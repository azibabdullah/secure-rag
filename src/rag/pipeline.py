from pathlib import Path
import re
import math
import sys
import time

from src.ingestion.loader import document_chunks, load_pages, load_parts, ocr_available
from src.llm.ollama_client import OllamaClient
from src.security.classifier import InjectionClassifier, SecurityCheckError, validated_score
from src.security.output_guard import redact
from src.security.hidden_rules import hidden_instruction
from src.storage.store import VectorStore, text_hash
from src.storage.conversations import Conversations
from src.utils.app_paths import DOCUMENT_GUARD_MODEL
from src.utils.audit import AuditLog
from src.utils.settings import load_settings, save_settings
from src.utils.operations import checkpoint, CancelledError


def packed_excerpts(excerpts, budget=4800):
    """Bound by UTF-8 bytes, including non-English input; never discard a tail."""
    groups, group, used = [], [], 0
    for text in excerpts:
        pieces, piece, size = [], [], 0
        for char in text:
            width = len(char.encode())
            if size + width > budget:
                pieces.append(''.join(piece))
                piece, size = [], 0
            piece.append(char)
            size += width
        if piece:
            pieces.append(''.join(piece))
        for part in pieces:
            width = len(part.encode()) + 2
            if group and used + width > budget:
                groups.append('\n\n'.join(group))
                group, used = [], 0
            group.append(part)
            used += width
    if group:
        groups.append('\n\n'.join(group))
    return groups


def focused_evidence(question, approved, byte_budget=1000):
    """Keep verbatim evidence for specific question terms through lossy summaries."""
    stop = {'the', 'a', 'an', 'of', 'in', 'on', 'and', 'or', 'to', 'this', 'that', 'its', 'is', 'are',
            'what', 'which', 'how', 'please', 'document', 'summarize', 'summarise', 'summary', 'explain', 'including'}
    terms = set(re.findall(r'\w+', question.lower())) - stop
    sentences = [(n, s.strip()) for n, h in enumerate(approved, 1)
                 for s in re.split(r'(?<=[.!?])\s+|\n+', h['text']) if s.strip()]
    frequencies = {term: sum(term in set(re.findall(r'\w+', s.lower())) for _, s in sentences) for term in terms}
    ranked = sorted(sentences, key=lambda pair: sum(math.log(1 + len(sentences)/(1+frequencies[t]))
                    for t in terms & set(re.findall(r'\w+', pair[1].lower()))), reverse=True)
    output, seen, used = [], set(), 0
    for number, sentence in ranked:
        if not terms & set(re.findall(r'\w+', sentence.lower())) or sentence in seen:
            continue
        text = f'[Excerpt {number}] {sentence}'
        if used + len(text.encode()) + 2 > byte_budget:
            continue
        output.append(text)
        seen.add(sentence)
        used += len(text.encode()) + 2
    return '\n'.join(output)


# Questions about the screening results themselves ("which documents were blocked?").
# They are answered from local screening records without calling the LLM, so no
# document text and no instruction in the question can reach a model.
_STATUS = r'(?:block\w*|allow\w*|approv\w*|quarantin\w*|reject\w*|flag\w*|accept\w*|screen\w*|pass(?:ed)?|fail\w*)'
_DOC = r'(?:documents?|docs?|files?|pdfs?|uploads?|passages?)'
LIBRARY_REPORT_PATTERNS = [
    re.compile(_DOC + r'\b[^.?!\n]{0,40}?\b(?:have|has|had|were|was|are|is|got|get|been)\s+(?:been\s+|not\s+)?' + _STATUS, re.I),
    re.compile(r'\b' + _STATUS + r'\s+(?:and\s+(?:which\s+|what\s+)?\w+\s+)?' + _DOC + r'\b', re.I),
    re.compile(r'\b' + _DOC + r'\s+(?:that\s+|which\s+)?(?:' + _STATUS + r')\b', re.I),
    re.compile(r'\b(?:library|uploads?|screening|scan|quarantine|documents|files)\s+(?:report|status|results?)\b', re.I),
    re.compile(r'\b(?:status|report)\s+(?:of|on|about|for)\s+(?:all\s+)?(?:the\s+|my\s+|these\s+)?' + _DOC + r'\b', re.I),
]


def _sentence_case(label):
    """'Text annotation on page 1' -> 'text annotation on page 1'; acronyms such as 'PDF ...' are kept."""
    return label if len(label) > 1 and label[1].isupper() else label[:1].lower() + label[1:]


def _chunks_of(text):
    from src.ingestion.loader import chunk_text
    return chunk_text(text) or [text]


def is_library_report(question):
    return len(question) <= 400 and any(p.search(question) for p in LIBRARY_REPORT_PATTERNS)


def _document_state(d):
    if d.get('status') == 'DEFERRED':
        return 'Unchecked'
    if not d.get('indexed_chunks'):
        return 'Blocked'
    return 'Partially approved' if d.get('quarantined_chunks') else 'Approved'


# "Tell me about this document", "what do these files represent", "key points": whole-document questions.
# Their wording rarely resembles the content, so they read every approved passage instead of a similarity search.
_SUBJECT = r'(?:document|documents|doc|docs|file|files|pdf|pdfs|report|reports|these|this|they|them|it|those|upload|uploads|library)'
OVERVIEW_PATTERN = re.compile(
    r'\b(?:summar(?:ize|ise|y|ies)|overview|outline|gist|tl;?dr|key\s+points|main\s+points|highlights|key\s+takeaways)\b'
    r'|\b(?:tell|teach|show)\s+me\s+(?:all\s+|more\s+|everything\s+)?about\b'
    r'|\bwhat\s+(?:is|are|was|were|does|do)\b.{0,40}?\b' + _SUBJECT + r'\b.{0,40}?\b(?:about|say|says|contain|contains|cover|covers|represent|represents|mean|means|for|do)\b'
    r'|\b(?:explain|elaborate|describe|walk\s+me\s+through|go\s+through)\b.{0,40}?\b' + _SUBJECT + r'\b', re.I | re.S)
LIBRARY_WORDS = re.compile(r'\b(?:documents?|docs?|files?|pdfs?|uploads?|uploaded|library)\b', re.I)
MAX_OVERVIEW_PASSAGES = 80          # whole-library overviews above this ask the user to select documents
SELECTED_FALLBACK_PASSAGES = 4      # selected documents with no similar passage: use the closest ones anyway


def is_overview_question(question):
    return bool(OVERVIEW_PATTERN.search(question))


AUTO_RAG_MIN_SIMILARITY = 0.45   # Chat mode: a passage must be at least this related to be used
WITHHELD_MARGIN = 0.05           # A blocked passage this much more relevant than any approved one wins
CHANNEL_NAMES = {'metadata': 'document properties (metadata)', 'annotation': 'an annotation or sticky note',
                 'comment': 'a reviewer comment', 'form_field': 'a form field', 'attachment': 'an embedded file',
                 'javascript': 'embedded JavaScript', 'bookmark': 'a bookmark title', 'header': 'a page header',
                 'footer': 'a page footer', 'footnote': 'a footnote or endnote', 'link': 'a link target',
                 'tracked_change': 'a tracked change', 'unrendered': 'text outside the main body',
                 'field_code': 'a field code', 'alt_text': 'image alt text', 'image_text': 'text inside an image (OCR)',
                 'invisible_text': 'invisible Unicode characters', 'glossary': 'a glossary part',
                 'unreadable': 'a part that could not be read'}


def _scope(source):
    """None (all documents) or a list of selected document paths."""
    if not source:
        return None
    return [source] if isinstance(source, str) else list(dict.fromkeys(str(s) for s in source))


class SecureRAG:
    def __init__(self):
        device = 'cpu' if getattr(sys, 'frozen', False) else None
        # PromptGuard: frozen FINAL model (direct user messages and conversation history).
        self.classifier = InjectionClassifier(device=device)
        # DocumentGuard: v3 seed 2 model with its own threshold (upload and retrieval screening).
        self.doc_classifier = InjectionClassifier(model_dir=DOCUMENT_GUARD_MODEL, device=device)
        self.audit = AuditLog()
        self.store = VectorStore()
        self.conversations = Conversations(self.store.vault)
        self.llm = OllamaClient(load_settings()['ollama_model'])

    def available_models(self):
        return self.llm.available_models()

    def set_model(self, name):
        if name not in self.llm.available_models():
            raise ValueError(f'Ollama model is not installed: {name}')
        self.llm.model = name
        self.preferences({'ollama_model': name})
        return name

    def preferences(self, changes):
        allowed = {'dark', 'motion', 'ocr', 'ollama_model', 'screen_documents_on_upload', 'starfield', 'logo_glow'}
        if set(changes) - allowed:
            raise ValueError('Unsupported preference')
        for key in ('dark', 'motion', 'ocr', 'screen_documents_on_upload', 'starfield', 'logo_glow'):
            if key in changes and not isinstance(changes[key], bool):
                raise ValueError('Invalid preference value')
        settings = load_settings()
        settings.update(changes)
        save_settings(settings)
        return settings

    def _doc_score(self, text):
        scores = self.doc_classifier.score([text])
        if len(scores) != 1:
            raise SecurityCheckError('Classifier returned an incomplete result. Upload stopped.')
        return validated_score(scores[0])

    def ingest(self, filename):
        source = str(Path(filename).resolve())
        checkpoint('Reading document')
        pages, hidden = load_parts(source, ocr=load_settings().get('ocr', False))
        digest = text_hash('\n\n'.join(p['text'] for p in pages) + '\n\x00hidden\n' +
                           '\n\n'.join(f"{h['channel']}:{h['text']}" for h in hidden))
        screen = load_settings().get('screen_documents_on_upload', True)
        duplicate = self.store.duplicate(digest, source)
        if duplicate and duplicate.get('screened_on_upload', True) == screen:
            return {k: v for k, v in duplicate.items() if k not in {'chunks', 'hidden_parts'}} | {'duplicate': True}
        chunks = document_chunks(pages)
        # Hidden channels are screened but never indexed: they can block the document, never reach the model.
        hidden_rows = []
        for part in hidden:
            pieces = [part['text']] if part.get('forced') else [t for t in _chunks_of(part['text'])]
            for text in pieces:
                hidden_rows.append({'channel': part['channel'], 'label': part['label'], 'page': part.get('page'),
                                    'text': text, 'forced': part.get('forced'), 'part_index': len(hidden_rows)})
        threshold = self.doc_classifier.threshold
        block_reason = None
        if screen:
            for index, row in enumerate(hidden_rows):
                checkpoint(f'Screening hidden content {index + 1} of {len(hidden_rows)} ({row["label"]})')
                row['score'] = self._doc_score(row['text']) if row['text'] else None
                rule = hidden_instruction(row['text'])
                if rule:
                    row['rule'] = {'why': rule[0], 'matched': rule[1]}
                row['decision'] = 'QUARANTINED' if row['forced'] or rule or (row['score'] or 0) >= threshold else 'SAFE'
            flagged = [r for r in hidden_rows if r['decision'] == 'QUARANTINED']
            if flagged:
                top = max(flagged, key=lambda r: (bool(r['forced']), (r['score'] or 0) >= threshold, r['score'] or 0))
                if top['forced']:
                    block_reason = f"{top['label']}: {top['forced']}"
                elif (top['score'] or 0) >= threshold:
                    block_reason = f"its {_sentence_case(top['label'])} scored {top['score']:.3f}, at or above the DocumentGuard threshold {threshold:.3f}"
                else:
                    block_reason = (f"its {_sentence_case(top['label'])} {top['rule']['why']} "
                                    f"(matched \u201c{top['rule']['matched']}\u201d; classifier score {top['score']:.3f})")
                if len(flagged) > 1:
                    block_reason += f'; {len(flagged) - 1} more hidden part' + ('s' if len(flagged) > 2 else '') + ' also flagged'
        else:
            for row in hidden_rows:
                row.update(score=None, decision='DEFERRED')
        for index, row in enumerate(chunks):
            if not screen:
                checkpoint(f'Preparing unchecked passage {index + 1} of {len(chunks)}')
                row.update(score=None, decision='DEFERRED')
                continue
            checkpoint(f'Screening excerpt {index + 1} of {len(chunks)}')
            score = self._doc_score(row['text'])
            row.update(score=score, decision='QUARANTINED' if score >= threshold else 'SAFE')
            if block_reason and row['decision'] == 'SAFE':
                # A malicious hidden channel blocks the whole file: nothing from it may be used.
                row.update(decision='QUARANTINED', blocked_by=block_reason)
        blocked = sum(r['decision'] == 'QUARANTINED' for r in chunks)
        result = {'source': source, 'status': 'DEFERRED' if not screen else (('PARTIAL' if blocked < len(chunks) else 'QUARANTINED') if blocked else 'SAFE'),
                  'indexed_chunks': len(chunks)-blocked, 'quarantined_chunks': blocked,
                  'approved_chunks': len(chunks)-blocked if screen else 0,
                  'deferred_chunks': len(chunks) if not screen else 0,
                  'screened_on_upload': screen, 'threshold': threshold,
                  'hidden_checked': len(hidden_rows) if screen else 0,
                  'hidden_flagged': sum(r['decision'] == 'QUARANTINED' for r in hidden_rows),
                  'hidden_channels': sorted({r['channel'] for r in hidden_rows}),
                  'block_reason': block_reason}
        self.store.replace_source(source, chunks, result={**result, 'hidden_parts': hidden_rows}, content_hash=digest)
        for row in hidden_rows:
            self.audit.record('ingestion_hidden_part', source=source, channel=row['channel'], label=row['label'],
                              decision=row['decision'], score=row['score'], sha256=text_hash(row['text']))
        for row in chunks:
            self.audit.record('ingestion_chunk', source=source, chunk_index=row['chunk_index'],
                              decision=row['decision'], score=row['score'], sha256=text_hash(row['text']))
        self.audit.record('document', **result)
        return result

    def ingest_many(self, filenames):
        results = []
        filenames = list(dict.fromkeys(filenames))
        for index, filename in enumerate(filenames):
            try:
                checkpoint(f'Uploading file {index + 1} of {len(filenames)}: {Path(filename).name}')
                results.append({'filename': filename, 'result': self.ingest(filename)})
            except CancelledError:
                return {'files': results, 'cancelled': True, 'remaining': filenames[index:]}
            except Exception as exc:
                results.append({'filename': filename, 'error': str(exc)})
        return {'files': results, 'cancelled': False, 'remaining': []}

    def document_decision(self, source):
        document = self.store.document(source)
        if not document:
            raise ValueError('Document is no longer in the library.')
        threshold = document.get('threshold', self.doc_classifier.threshold)
        rows = []
        for row in document['chunks']:
            score = row.get('score')
            decision = row.get('decision', 'SAFE')
            if decision == 'DEFERRED':
                reason = 'Upload screening was disabled. This passage is stored, not approved. It must pass DocumentGuard when retrieved.'
            elif score is None:
                reason = 'Imported from the earlier approved library. The original classifier score is unavailable; retrieval screening is still required.'
            elif row.get('blocked_by'):
                reason = (f'This passage scored {score:.6f} (below the threshold {threshold:.3f}) but the whole document '
                          f"is blocked because {row['blocked_by']}.")
            else:
                reason = (f'Malicious score {score:.6f} is ' +
                    ('at or above' if decision == 'QUARANTINED' else 'below') + f' the upload threshold {threshold:.3f}.')
            rows.append({**row, 'reason': reason})
        hidden = []
        for row in document.get('hidden_parts', []):
            where = CHANNEL_NAMES.get(row['channel'], row['channel'])
            if row.get('decision') == 'DEFERRED':
                reason = 'Upload screening was disabled; hidden content was not checked. It is never indexed.'
            elif row.get('forced'):
                reason = row['forced']
            elif row.get('rule') and row.get('decision') == 'QUARANTINED' and (row.get('score') or 0) < threshold:
                reason = (f"Found in {where}. The hidden-content rule flagged it because it {row['rule']['why']} "
                          f"(matched \u201c{row['rule']['matched']}\u201d). Classifier score {row['score']:.6f} was below "
                          f'{threshold:.3f}, but hidden content has no legitimate reason to instruct an AI.')
            else:
                reason = (f"Found in {where}. Score {row['score']:.6f} is " +
                          ('at or above' if row['decision'] == 'QUARANTINED' else 'below') + f' the threshold {threshold:.3f}. '
                          'Hidden content is screened but never sent to the model.')
            hidden.append({**row, 'reason': reason})
        meta = {k: v for k, v in document.items() if k not in {'chunks', 'hidden_parts'}}
        return {'document': meta, 'threshold': threshold, 'retrieval_threshold': self.doc_classifier.threshold,
                'rows': rows, 'hidden_parts': hidden, 'block_reason': document.get('block_reason'),
                'explanation': ('DocumentGuard (v3 seed 2) scores every passage and every hidden part of the file: metadata, '
                    'annotations, comments, form fields, attachments, scripts, headers, tracked changes and invisible text. '
                    'Hidden parts are also checked by explainable rules for instructions aimed at an AI. '
                    'A malicious hidden part blocks the entire document. The classifier returns a score, not a written reasoning '
                    'trace; scores are not calibrated certainty, approval is not proof of safety, and a block can be a false '
                    'positive. Images are read only when local OCR is on.')}

    def remove_document(self, source):
        self.store.delete_source(source)
        result = {'source': source, 'status': 'DELETED', 'indexed_chunks': 0, 'quarantined_chunks': 0}
        self.audit.record('document', **result)
        return result

    def _checked_answer(self, answer, source_count):
        checkpoint('Checking response for exposed credentials and email addresses')
        checked, redactions = redact(answer)
        total = sum(redactions.values()) if isinstance(redactions, dict) else 0
        self._step('Output check', f'{total} credential or email redaction' + ('' if total == 1 else 's') if total
                   else 'No credentials or email addresses in the answer', 'warn' if total else 'ok')
        self.audit.record('response', decision='RETURNED', source_count=source_count, redactions=redactions)
        return checked

    def _withheld_candidates(self, question, scope, min_similarity):
        """Quarantined passages related to the question, so a refusal can say exactly what was withheld and why."""
        documents = self.store.documents()
        if not isinstance(documents, list):
            return []
        rows = [(d, r) for d in documents if scope is None or d['source'] in scope
                for r in d.get('chunks', []) if r.get('decision') == 'QUARANTINED' and r.get('text')]
        if not rows:
            return []
        checkpoint('Checking whether the question targets quarantined passages')
        vectors = self.store.encoder.encode([question] + [r['text'] for _, r in rows], normalize_embeddings=True)
        query = vectors[0]
        found = []
        for (document, row), vector in zip(rows, vectors[1:]):
            similarity = float(sum(float(a) * float(b) for a, b in zip(query, vector)))
            if similarity >= min_similarity:
                found.append(self._trail(document['source'], row, 'upload', similarity, document.get('threshold')))
        return found

    def _trail(self, source, row, stage, relevance, threshold=None):
        threshold = threshold if threshold is not None else self.doc_classifier.threshold
        score = row.get('score')
        if row.get('blocked_by'):
            why = f"the whole document is blocked because {row['blocked_by']}"
        elif stage == 'retrieval':
            why = f'it scored {score:.3f} at the retrieval-time check (threshold {threshold:.3f})'
        else:
            why = f'it scored {score:.3f} at upload, at or above the threshold {threshold:.3f}'
        return {'source': source, 'name': Path(source).name, 'passage': row.get('chunk_index', 0) + 1,
                'page': row.get('page'), 'section': row.get('section'), 'score': score, 'threshold': threshold,
                'stage': stage, 'relevance': relevance, 'guard': 'DocumentGuard', 'reason': why}

    def _withheld_result(self, withheld, approved_count, auto=False):
        lines = ['I can\'t answer this from your documents. The passages most related to your question were quarantined by '
                 'DocumentGuard, so they were never shown to the language model.', '', 'Why:']
        for w in withheld:
            where = f"{w['name']}, passage {w['passage']}" + (f" (page {w['page']})" if w['page'] else '')
            lines.append(f"- {where}: withheld because {w['reason']}. Relevance to your question: {w['relevance']:.2f}.")
        lines += ['', ('Other approved passages were less related to the question, so answering from them could mislead.'
                       if approved_count else 'No approved passage was related enough to answer instead.'),
                  'Select a passage below to see its full screening decision. A block can be a false positive: '
                  'the classifier gives a score, not a reason.']
        self.audit.record('query', decision='WITHHELD', reason='Question targets quarantined passages',
                          withheld=len(withheld), auto=auto)
        return {'status': 'WITHHELD', 'answer': '\n'.join(lines), 'sources': [], 'withheld': withheld,
                'used_documents': True}

    def _step(self, step, detail, status='ok'):
        """One timed entry in the pipeline trace shown by the Security inspector."""
        now = time.perf_counter()
        steps = getattr(self, '_steps', None)
        if steps is None:
            return
        steps.append({'step': step, 'detail': detail, 'status': status, 'ms': round((now - self._step_clock) * 1000)})
        self._step_clock = now

    def ask(self, question, mode='chat', source=None, overview=False, session_id=None, report=False):
        self._steps, self._step_clock, self._guard = [], time.perf_counter(), None
        started = self._step_clock
        try:
            result = self._ask(question, mode, source, overview, session_id, report)
            result = {**result, 'trace': self._steps, 'guard': self._guard,
                      'model': getattr(self.llm, 'model', None) if isinstance(getattr(self.llm, 'model', None), str) else None,
                      'elapsed_ms': round((time.perf_counter() - started) * 1000)}
            if session_id:
                self.conversations.append(session_id, question.strip(), result, mode, source)
            return result
        finally:
            self._steps = None

    def _ask(self, question, mode, source, overview, session_id, report):
        checkpoint('Checking your message')
        question = question.strip()
        if not question:
            raise ValueError('Enter a message')
        if mode not in {'chat', 'documents'}:
            raise ValueError('Unknown chat mode')
        if len(question.encode()) > 1800:
            raise ValueError('Please shorten this message to 1,800 UTF-8 bytes so there is room for references.')
        scope = _scope(source) if mode == 'documents' else None
        if report or is_library_report(question):
            self._step('Screening records', 'Answered from local upload decisions; no model call')
            return self.library_report(scope, question)
        guard = self.classifier.classify(question)
        score = validated_score(guard['score'])
        if guard['label'] not in {'SAFE', 'MALICIOUS'} or (score >= self.classifier.threshold) != (guard['label'] == 'MALICIOUS'):
            raise SecurityCheckError('Inconsistent security decision. Request stopped.')
        blocked = score >= self.classifier.threshold
        self._guard = {'prompt_score': score, 'prompt_threshold': self.classifier.threshold}
        self._step('Prompt screening', f'PromptGuard {score:.3f} ' + ('at or above' if blocked else 'below') +
                   f' {self.classifier.threshold:.3f}', 'blocked' if blocked else 'ok')
        self.audit.record('query', decision='BLOCKED' if blocked else 'SAFE', reason='PromptGuard', score=score)
        if blocked:
            return {'status': 'BLOCKED', 'sources': [],
                    'answer': ('PromptGuard blocked this message before it reached the local model.\n\n'
                               f'Why: the prompt-injection classifier scored it {score:.3f}, at or above the PromptGuard threshold '
                               f'{self.classifier.threshold:.3f}. The score measures how closely the wording resembles known '
                               'prompt-injection attacks. It is not a judgement of your intent, and it can be a false positive.\n\n'
                               'What you can do: rephrase the question as a plain request, without instruction-like wording '
                               '(for example "ignore", "override", "act as", "system prompt"). To see which documents were '
                               'blocked or allowed, use Screening report.'),
                    'trail': {'guard': 'PromptGuard', 'model': 'FINAL (DeBERTa-v3-small, authz-v2)', 'score': score,
                              'threshold': self.classifier.threshold, 'stage': 'Before the model'}}
        turns = self.conversations.history(session_id, mode, source) if session_id else []
        history = []
        for turn in turns:
            # Past responses are not promoted to system instructions. Screen both roles again.
            for role, content in [('user', turn['question']), ('assistant', turn['result']['answer'])]:
                if validated_score(self.classifier.score([content])[0]) < self.classifier.threshold:
                    history.append({'role': role, 'content': content})
        if mode == 'chat':
            result = self._ask_chat(question, history)
        else:
            result = self._ask_documents(question, scope, overview, history)
        checkpoint()
        return result

    def _ask_chat(self, question, history):
        """General chat that uses the library automatically when the question is related to it."""
        checkpoint('Looking for related passages in your documents')
        if is_overview_question(question) and LIBRARY_WORDS.search(question):
            # "What are my documents about?" in Chat: answer from the whole approved library.
            self._step('Library search', 'Whole-library question; reading every approved document')
            return self._ask_documents(question, None, True, history)
        hits = self.store.retrieve(question, min_similarity=AUTO_RAG_MIN_SIMILARITY)
        hits = hits if isinstance(hits, list) else []
        self._step('Library search', f'{len(hits)} related passage' + ('' if len(hits) == 1 else 's') +
                   f' (similarity at least {AUTO_RAG_MIN_SIMILARITY:.2f})' if hits else 'No related passages; answering without documents')
        if hits or self._withheld_candidates(question, None, AUTO_RAG_MIN_SIMILARITY):
            result = self._ask_documents(question, None, False, history, candidates=hits,
                                         min_similarity=AUTO_RAG_MIN_SIMILARITY, auto=True)
            if result['status'] != 'NO_CONTEXT':
                return result
        answer = self.llm.answer_general(question, history=history) if history else self.llm.answer_general(question)
        self._step('Generation', f'{self.llm.model} · local' if isinstance(getattr(self.llm, 'model', None), str) else 'Local model')
        return {'status': 'ANSWERED', 'answer': self._checked_answer(answer, 0), 'sources': [], 'used_documents': False}

    def _ask_documents(self, question, scope, overview, history, candidates=None, min_similarity=0.35, auto=False):
        overview = overview or is_overview_question(question)
        if auto:
            overview = False
        if overview and not scope:
            # Nothing selected means "all documents": use the whole library when it is small enough.
            documents = self.store.documents()
            usable = [d for d in documents if d.get('indexed_chunks')] if isinstance(documents, list) else []
            if usable and sum(d['indexed_chunks'] for d in usable) <= MAX_OVERVIEW_PASSAGES:
                scope = [d['source'] for d in usable]
                scope += [d['source'] for d in documents if not d.get('indexed_chunks')]  # blocked files: explained, never used
            else:
                return {'status': 'SELECT_DOCUMENT', 'sources': [], 'answer': (
                    'Select one or more documents, then ask for an overview.' if not usable else
                    f'The library has more than {MAX_OVERVIEW_PASSAGES} approved passages. Select the documents to summarize.')}
        checkpoint('Finding relevant excerpts')
        # A bounded previous user question supplies nouns for short follow-ups.
        retrieval_query = question
        if history and re.search(r'\b(it|that|those|they|this|more|elaborate)\b', question, re.I):
            previous = next((h['content'] for h in reversed(history) if h['role'] == 'user'), '')
            retrieval_query = previous[:1000] + '\n' + question
        if candidates is None:
            if overview:
                candidates = [c for s in scope for c in self.store.source_chunks(s)]
            else:
                source_filter = scope[0] if scope and len(scope) == 1 else scope
                candidates = self.store.retrieve(retrieval_query, source=source_filter)
        approved, blocked_now = [], []
        for number, hit in enumerate(candidates, 1):
            checkpoint(f'Checking reference {number} of {len(candidates)}')
            if text_hash(hit['text']) != hit['sha256']:
                self.store.record_retrieval_check(hit, 'INTEGRITY_BLOCKED')
                self.audit.record('retrieved_chunk', decision='BLOCKED', reason='SHA-256 mismatch', chunk_id=hit['id'])
                continue
            score = validated_score(self.doc_classifier.score([hit['text']])[0])
            self.store.record_retrieval_check(hit, 'BLOCKED' if score >= self.doc_classifier.threshold else 'SAFE', score)
            self.audit.record('retrieved_chunk', decision='BLOCKED' if score >= self.doc_classifier.threshold else 'SAFE', reason='DocumentGuard', score=score, chunk_id=hit['id'])
            if score < self.doc_classifier.threshold:
                approved.append(hit)
            else:
                blocked_now.append(self._trail(hit['source'], {**hit, 'score': score}, 'retrieval', hit.get('similarity') or 0))
            if not overview and len(approved) == 4:
                break
        if not overview and not approved and not blocked_now and scope:
            # The user chose these documents; a low similarity score is not a reason to ignore them.
            nearest = self.store.retrieve(retrieval_query, limit=SELECTED_FALLBACK_PASSAGES, min_similarity=-1.0,
                                          source=scope[0] if len(scope) == 1 else scope)
            for hit in (nearest if isinstance(nearest, list) else []):
                if text_hash(hit['text']) != hit['sha256']:
                    continue
                score = validated_score(self.doc_classifier.score([hit['text']])[0])
                self.store.record_retrieval_check(hit, 'BLOCKED' if score >= self.doc_classifier.threshold else 'SAFE', score)
                if score < self.doc_classifier.threshold:
                    approved.append(hit)
                else:
                    blocked_now.append(self._trail(hit['source'], {**hit, 'score': score}, 'retrieval', hit.get('similarity') or 0))
            if approved:
                self._step('Retrieval', f'No passage was closely similar; using the {len(approved)} closest approved passage(s) '
                           'from the selected documents', 'warn')
        if overview:
            withheld = [self._trail(d['source'], r, 'upload', 0.0, d.get('threshold'))
                        for d in (self.store.documents() if isinstance(self.store.documents(), list) else [])
                        if d['source'] in scope for r in d.get('chunks', []) if r.get('decision') == 'QUARANTINED']
        else:
            withheld = self._withheld_candidates(retrieval_query, scope, min_similarity)
        withheld = sorted(blocked_now + withheld, key=lambda w: -w['relevance'])[:5]
        self._step('Context screening', f'DocumentGuard re-checked {len(approved) + len(blocked_now)} passage' +
                   ('' if len(approved) + len(blocked_now) == 1 else 's') + f': {len(approved)} approved, {len(blocked_now)} blocked' +
                   (f'; {len(withheld)} related passage(s) withheld' if withheld else ''),
                   'warn' if withheld else 'ok')
        best_approved = max((h.get('similarity') or 0 for h in approved), default=0)
        if withheld and (not approved or (not overview and withheld[0]['relevance'] >= best_approved + WITHHELD_MARGIN)):
            return self._withheld_result(withheld, len(approved), auto)
        if not approved:
            names = ', '.join(Path(s).name for s in scope[:4]) + (f' and {len(scope) - 4} more' if scope and len(scope) > 4 else '') if scope else 'your library'
            return {'status': 'NO_CONTEXT', 'sources': [], 'answer': (
                f'No approved passage in {names} could answer this. ' + (
                'None of the selected documents has an approved passage: each one is blocked or unchecked. '
                'Open Explain decision to see why.' if scope else
                'No passage was related closely enough to your question. Select documents in the Documents view, '
                'or rephrase with words that appear in the document.'))}
        excerpts = [f"[Excerpt {n}] {Path(h['source']).name}; page {h.get('page') or 'n/a'}; {h.get('section', '')}\n{h['text']}" for n, h in enumerate(approved, 1)]
        groups = packed_excerpts(excerpts, budget=max(2000, 6000-len(question.encode())))
        if len(groups) > 1:
            evidence = focused_evidence(question, approved)
            note_budget = max(1500, 5800 - len(question.encode()) - len(evidence.encode()))
            notes = []
            for n, context in enumerate(groups, 1):
                checkpoint(f'Summarizing section {n} of {len(groups)}')
                note = self.llm.answer_documents('Extract the facts relevant to: ' + question + '\nUse at most 120 words. Preserve original [Excerpt N] citations.', context)
                notes.append(self._checked_answer(note, len(approved)))
            # Hierarchical reduction visits all sections, never only the opening pages.
            for level in range(8):
                reduced_groups = packed_excerpts(notes, budget=note_budget)
                if len(reduced_groups) == 1:
                    break
                checkpoint(f'Combining document sections, pass {level + 1}')
                reduced = [self._checked_answer(self.llm.answer_documents(
                    'Condense these notes to at most 100 words, preserving facts and original [Excerpt N] citations. Question: ' + question, g), len(approved)) for g in reduced_groups]
                if sum(len(n) for n in reduced) >= sum(len(n) for n in notes):
                    raise RuntimeError('The local model did not condense the summary. Try another model; no incomplete summary was saved.')
                notes = reduced
            else:
                raise RuntimeError('Summary exceeded the reduction limit. Split the document into smaller files.')
            context = reduced_groups[0] + '\n\nVerbatim supporting excerpts:\n' + evidence
        else:
            context = groups[0]
        checkpoint('Writing final answer')
        answer = self.llm.answer_documents(question, context, history=history) if history else self.llm.answer_documents(question, context)
        self._step('Generation', (f'{self.llm.model} · local' if isinstance(getattr(self.llm, 'model', None), str) else 'Local model') +
                   f' · {len(approved)} excerpt' + ('' if len(approved) == 1 else 's'))
        cited = {int(n) for n in re.findall(r'\[Excerpt\s+(\d+)\]', answer, re.I)}
        invalid = cited - set(range(1, len(approved)+1))
        if invalid:
            raise RuntimeError('The model produced an invalid citation. Retry; this answer was not saved.')
        if overview:
            answer += f'\n\nCoverage: {len(approved)} approved excerpts processed from {len(candidates)} indexed excerpts. Quarantined content is excluded.'
        if withheld:
            answer += ('\n\nNote: ' + str(len(withheld)) + ' related passage' + (' was' if len(withheld) == 1 else 's were') +
                       ' withheld by DocumentGuard and not used. See the details below.')
        return {'status': 'ANSWERED', 'answer': self._checked_answer(answer, len(approved)),
                'sources': [{**h, 'citation': n, 'cited': n in cited} for n, h in enumerate(approved, 1)],
                'withheld': withheld, 'used_documents': True,
                'documents_used': sorted({Path(h['source']).name for h in approved}),
                'citation_note': 'Cited means the model referenced this excerpt; it is not an automatic proof of claim support.'}

    def library_report(self, source=None, question=''):
        """Screening report built from stored decisions. No model call; no passage text."""
        checkpoint('Reading screening records')
        scope = _scope(source)
        documents = [d for d in self.store.documents() if not scope or d['source'] in scope]
        order = {'Blocked': 0, 'Partially approved': 1, 'Unchecked': 2, 'Approved': 3}
        rows = []
        for d in documents:
            state = _document_state(d)
            chunks = d.get('chunks', [])
            scores = [c['score'] for c in chunks if isinstance(c.get('score'), (int, float))]
            flagged = [{'passage': c['chunk_index'] + 1, 'page': c.get('page'), 'score': c.get('score')}
                       for c in sorted(chunks, key=lambda c: c['chunk_index']) if c.get('decision') == 'QUARANTINED']
            rows.append({'source': d['source'], 'name': Path(d['source']).name, 'state': state,
                         'passages': len(chunks), 'usable': d.get('indexed_chunks', 0),
                         'quarantined': d.get('quarantined_chunks', 0),
                         'highest_score': max(scores) if scores else None,
                         'threshold': d.get('threshold'), 'flagged': flagged,
                         'block_reason': d.get('block_reason'), 'hidden_checked': d.get('hidden_checked', 0),
                         'hidden_flagged': d.get('hidden_flagged', 0)})
        rows.sort(key=lambda r: (order[r['state']], r['name'].lower()))
        counts = {k: sum(r['state'] == k for r in rows) for k in order}
        if not rows:
            answer = 'No documents are in the library yet.' if not scope else 'The selected documents are no longer in the library.'
        else:
            lines = [f"Screening report for {len(rows)} document{'s' if len(rows) != 1 else ''}: "
                     f"{counts['Approved']} approved, {counts['Partially approved']} partially approved, "
                     f"{counts['Blocked']} blocked" + (f", {counts['Unchecked']} unchecked" if counts['Unchecked'] else '') + '.']
            for state in order:
                group = [r for r in rows if r['state'] == state]
                if not group:
                    continue
                lines.append(f'\n{state}:')
                for r in group:
                    detail = f"{r['usable']} of {r['passages']} passage{'s' if r['passages'] != 1 else ''} usable"
                    if r['block_reason']:
                        detail += f"; whole document blocked: {r['block_reason']}"
                    elif r['flagged']:
                        detail += '; quarantined ' + ', '.join(
                            f"passage {f['passage']}" + (f" (page {f['page']})" if f['page'] else '') +
                            (f" score {f['score']:.3f}" if isinstance(f['score'], (int, float)) else '') for f in r['flagged'])
                    lines.append(f"- {r['name']}: {detail}")
            lines.append('\nBuilt from DocumentGuard upload records; no language model was used. '
                         'Retrieved passages are checked again before they reach the model.')
            answer = '\n'.join(lines)
        self.audit.record('query', decision='REPORT', reason='Library report from local records (no model call)',
                          documents=len(rows))
        return {'status': 'REPORT', 'answer': answer, 'sources': [],
                'report': {'documents': rows, 'counts': counts,
                           'document_threshold': self.doc_classifier.threshold, 'scope': scope}}

    def snapshot(self):
        return {'documents': [{k: v for k, v in d.items() if k not in {'chunks', 'hidden_parts'}} for d in self.store.documents()],
                'events': self.audit.recent(), 'model': self.llm.model, 'preferences': load_settings(),
                'sessions': self.conversations.list(), 'ocr_available': ocr_available(),
                'legacy_storage': self.store.legacy_present,
                'guards': {'prompt': {'name': 'PromptGuard', 'model': 'FINAL · DeBERTa-v3-small (authz-v2)',
                                      'threshold': self.classifier.threshold},
                           'document': {'name': 'DocumentGuard', 'model': 'v3 seed 2 · DeBERTa-v3-small',
                                        'threshold': self.doc_classifier.threshold}}}
