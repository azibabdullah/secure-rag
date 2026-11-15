from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from xml.etree import ElementTree

from docx import Document
from pypdf import PdfReader
from src.utils.operations import checkpoint

SUPPORTED = {'.pdf', '.docx', '.txt', '.md'}
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000


def ocr_available():
    return bool(shutil.which('tesseract'))


def _tesseract(image):
    executable = shutil.which('tesseract')
    if not executable:
        raise RuntimeError('OCR needs local Tesseract on PATH. Install it and restart SecureRAG, or upload a text PDF.')
    process = subprocess.Popen([executable, str(image), 'stdout', '-l', 'eng'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    deadline = time.monotonic() + 120
    try:
        while True:
            checkpoint()
            if time.monotonic() > deadline:
                raise TimeoutError('OCR timed out for this page.')
            try:
                output, error = process.communicate(timeout=0.15)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise RuntimeError('OCR failed: ' + error.decode(errors='replace')[:300])
        return output.decode('utf-8', errors='replace')
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def _ocr_page(data, index):
    if not shutil.which('tesseract'):
        raise RuntimeError('OCR needs local Tesseract on PATH. Install it and restart SecureRAG, or upload a text PDF.')
    import pypdfium2 as pdfium
    with tempfile.TemporaryDirectory(prefix='securerag-ocr-') as folder:
        image = Path(folder) / 'page.png'
        with pdfium.PdfDocument(data) as pdf:
            page = pdf[index]
            if page.get_width() * page.get_height() * 4 > 40_000_000:
                raise ValueError('PDF page is too large to render safely for OCR.')
            bitmap = page.render(scale=2)
            bitmap.to_pil().save(image)
            bitmap.close()
            page.close()
        return _tesseract(image)


def _ocr_image(content, suffix):
    with tempfile.TemporaryDirectory(prefix='securerag-ocr-') as folder:
        image = Path(folder) / ('image' + suffix)
        image.write_bytes(content)
        return _tesseract(image)


# ---------------------------------------------------------------------------
# Hidden channels. Everything a file carries besides its visible page text:
# metadata, annotations/comments, form fields, bookmarks, scripts, link
# targets, attachments, tracked changes, text boxes, alt text, invisible
# Unicode. These are screened by DocumentGuard but never indexed, so they can
# block a document but can never reach the language model.
# ---------------------------------------------------------------------------
MAX_HIDDEN_CHARS = 400_000
MAX_ZIP_BYTES = 200 * 1024 * 1024
ZERO_WIDTH = re.compile('[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]')
TAG_CHARS = re.compile('[\U000E0000-\U000E007F]')
TEXT_SUFFIXES = {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.yaml', '.yml', '.log', '.ini', '.cfg', '.rtf'}
# Technical fields with no free text (dates, counters, flags) are not screened.
SKIP_METADATA = {'CreationDate', 'ModDate', 'Trapped', 'created', 'modified', 'lastPrinted', 'revision', 'TotalTime',
                 'Pages', 'Words', 'Characters', 'CharactersWithSpaces', 'Lines', 'Paragraphs', 'DocSecurity',
                 'ScaleCrop', 'LinksUpToDate', 'SharedDoc', 'HyperlinksChanged', 'AppVersion'}
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.webp'}


def clean_text(text):
    """Remove characters that render as nothing; they can split attack words past a classifier."""
    return TAG_CHARS.sub('', ZERO_WIDTH.sub('', text or ''))


def invisible_payload(text):
    """Decode Unicode tag characters (U+E0020-E007E), which carry ASCII text that no viewer shows."""
    return ''.join(chr(ord(c) - 0xE0000) for c in TAG_CHARS.findall(text or '') if 0x20 <= ord(c) - 0xE0000 <= 0x7E)


def _part(channel, label, text, page=None, forced=None):
    return {'channel': channel, 'label': label, 'page': page, 'section': label,
            'text': clean_text(str(text)).strip(), 'forced': forced}


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _xml(content):
    return ElementTree.fromstring(content)


def _paragraphs(root):
    """Paragraph text from WordprocessingML/DrawingML, or all text when there are no paragraphs."""
    lines = []
    for element in root.iter():
        if _local(element.tag) == 'p':
            text = ''.join(t.text or '' for t in element.iter() if _local(t.tag) in {'t', 'delText', 'instrText'})
            if text.strip():
                lines.append(text)
    if lines:
        return '\n'.join(lines)
    return '\n'.join(t.strip() for t in root.itertext() if t and t.strip())


def _decode_text(content):
    for encoding in ('utf-8-sig', 'utf-16'):
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        printable = sum(c.isprintable() or c in '\r\n\t' for c in text[:5000])
        if text and printable / max(1, len(text[:5000])) > 0.9:
            return text
    return None


def _zip_text(content, depth):
    """All XML text inside an Office (zip) container, e.g. an embedded spreadsheet."""
    texts = []
    with zipfile.ZipFile(BytesIO(content)) as archive:
        if sum(i.file_size for i in archive.infolist()) > MAX_ZIP_BYTES:
            raise ValueError('embedded archive is too large to inspect')
        for info in archive.infolist():
            if info.filename.lower().endswith(('.xml', '.rels')):
                try:
                    texts.append(_paragraphs(_xml(archive.read(info))))
                except ElementTree.ParseError:
                    continue
    return '\n'.join(t for t in texts if t.strip())


def _embedded_parts(name, content, channel, page, ocr, depth=0):
    """Text of an embedded file. A file that cannot be inspected blocks the document (fail closed)."""
    suffix = Path(name).suffix.lower()
    label = f"Embedded file '{name}'"
    try:
        if content[:4] == b'%PDF' and depth < 1:
            body, hidden = _pdf_parts(content, ocr, depth + 1)
            return ([_part(channel, label, '\n'.join(p['text'] for p in body), page)] +
                    [{**h, 'label': f"{label} > {h['label']}", 'section': f"{label} > {h['label']}"} for h in hidden])
        if content[:2] == b'PK':
            return [_part(channel, label, _zip_text(content, depth), page)]
        if suffix in IMAGE_SUFFIXES:
            if ocr:
                return [_part(channel, label + ' (OCR)', _ocr_image(content, suffix), page)]
            return []  # images are only readable with OCR; see the OCR setting
        text = _decode_text(content)
        if text is not None:
            return [_part(channel, label, text, page)]
    except Exception as exc:  # malformed embedded content must not pass silently
        return [_part(channel, label, f'[{label} could not be inspected: {str(exc)[:120]}]', page,
                      forced='Embedded content could not be inspected, so the document cannot be verified as safe.')]
    return [_part(channel, label, f'[{label}: binary content, {len(content)} bytes]', page,
                  forced='Embedded binary content cannot be inspected, so the document cannot be verified as safe.')]


def _pdf_string(value):
    try:
        value = value.get_object()
    except AttributeError:
        pass
    if hasattr(value, 'get_data'):
        return _decode_text(value.get_data()) or ''
    return str(value) if value is not None else ''


def _pdf_hidden(reader, ocr, depth):
    parts = []
    def guarded(label, function):
        try:
            function()
        except Exception as exc:
            parts.append(_part('unreadable', label, f'[{label} could not be read: {str(exc)[:120]}]',
                               forced=f'{label} could not be read, so it cannot be verified as safe.'))

    def metadata():
        info = reader.metadata or {}
        # One part per field, so a payload in Keywords is not diluted by harmless fields.
        for key, value in info.items():
            key = str(key).lstrip('/')
            text = _pdf_string(value)
            if text.strip() and key not in SKIP_METADATA:
                parts.append(_part('metadata', f'PDF metadata field "{key}"', f'{key}: {text}'))
        root = reader.trailer['/Root'].get_object()
        if '/Metadata' in root:
            xmp = root['/Metadata'].get_object().get_data()
            text = _paragraphs(_xml(xmp))
            if text.strip():
                parts.append(_part('metadata', 'PDF XMP metadata', text))

    def annotations():
        for number, page in enumerate(reader.pages, 1):
            for ref in page.get('/Annots') or []:
                annot = ref.get_object()
                subtype = str(annot.get('/Subtype', '/Annot')).lstrip('/')
                if subtype in {'Widget', 'Popup'}:
                    continue  # form widgets are read as form fields
                fields = []
                for key in ('/T', '/Subj', '/Contents'):
                    if key in annot and _pdf_string(annot[key]).strip():
                        fields.append(_pdf_string(annot[key]))
                if '/RC' in annot:
                    try:
                        fields.append(_paragraphs(_xml(_pdf_string(annot['/RC']).encode())))
                    except ElementTree.ParseError:
                        fields.append(re.sub(r'<[^>]+>', ' ', _pdf_string(annot['/RC'])))
                action = annot.get('/A')
                if action is not None:
                    action = action.get_object()
                    for key in ('/URI', '/JS', '/F'):
                        if key in action:
                            fields.append(_pdf_string(action[key]))
                text = '\n'.join(f for f in fields if f.strip())
                if text.strip():
                    channel = 'link' if subtype == 'Link' else 'annotation'
                    parts.append(_part(channel, f'{subtype} annotation on page {number}', text, number))

    def form_fields():
        for name, field in (reader.get_fields() or {}).items():
            values = [_pdf_string(field.get(k)) for k in ('/V', '/TU', '/TM', '/DV') if field.get(k) is not None]
            text = '\n'.join(v for v in values if v.strip() and v not in {'/Off', '/Yes'})
            if text.strip():
                parts.append(_part('form_field', f"Form field '{name}'", text))

    def outline():
        titles = []
        def walk(items):
            for item in items:
                if isinstance(item, list):
                    walk(item)
                elif getattr(item, 'title', None):
                    titles.append(str(item.title))
        walk(reader.outline or [])
        if titles:
            parts.append(_part('bookmark', 'PDF bookmarks', '\n'.join(titles)))

    def scripts():
        root = reader.trailer['/Root'].get_object()
        code = []
        names = root.get('/Names')
        if names is not None and '/JavaScript' in names.get_object():
            tree = names.get_object()['/JavaScript'].get_object()
            entries = list(tree.get('/Names') or [])
            for kid in tree.get('/Kids') or []:
                entries += list(kid.get_object().get('/Names') or [])
            for action in entries[1::2]:
                action = action.get_object()
                if '/JS' in action:
                    code.append(_pdf_string(action['/JS']))
        open_action = root.get('/OpenAction')
        if open_action is not None:
            open_action = open_action.get_object()
            if hasattr(open_action, 'get') and '/JS' in open_action:
                code.append(_pdf_string(open_action['/JS']))
        if code:
            parts.append(_part('javascript', 'PDF JavaScript', '\n'.join(code)))

    def attachments():
        for name, contents in (reader.attachments or {}).items():
            for content in contents:
                parts.extend(_embedded_parts(name, content, 'attachment', None, ocr, depth))

    for label, function in [('PDF metadata', metadata), ('PDF annotations', annotations), ('PDF form fields', form_fields),
                            ('PDF bookmarks', outline), ('PDF scripts', scripts), ('PDF attachments', attachments)]:
        guarded(label, function)
    return parts


def _pdf_parts(data, ocr, depth=0):
    reader = PdfReader(BytesIO(data))
    if len(reader.pages) > 500:
        raise ValueError('PDF exceeds the 500-page limit. Split it into smaller documents.')
    pages, hidden = [], []
    for number, page in enumerate(reader.pages, 1):
        checkpoint(f'Reading PDF page {number} of {len(reader.pages)}')
        text = page.extract_text() or ''
        method = 'extracted'
        if not text.strip():
            if not ocr:
                raise ValueError(f'Page {number} has no text. Enable local OCR before uploading; no partial document was indexed.')
            text = _ocr_page(data, number - 1)
            method = 'ocr'
            if not text.strip():
                raise ValueError(f'OCR found no text on page {number}. Review the PDF before indexing.')
        elif ocr:
            try:
                has_images = len(page.images) > 0
            except Exception:
                has_images = True
            if has_images:
                checkpoint(f'Reading text inside images on page {number}')
                image_text = _ocr_page(data, number - 1)
                if image_text.strip():
                    hidden.append(_part('image_text', f'Text in images on page {number} (OCR)', image_text, number))
        pages.append({'page': number, 'section': f'Page {number}', 'text': text, 'extraction': method})
    checkpoint('Inspecting metadata, annotations and attachments')
    hidden += _pdf_hidden(reader, ocr, depth)
    return pages, hidden


def _docx_hidden(data, body_text, ocr):
    parts = []
    body = re.sub(r'\s+', ' ', body_text)
    with zipfile.ZipFile(BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > MAX_ZIP_BYTES:
            raise ValueError('DOCX package is too large to inspect safely.')
        for info in archive.infolist():
            name, low = info.filename, info.filename.lower()
            content = archive.read(info)
            try:
                if low in {'docprops/core.xml', 'docprops/app.xml', 'docprops/custom.xml'}:
                    label = {'docprops/core.xml': 'Document properties', 'docprops/app.xml': 'Application properties',
                             'docprops/custom.xml': 'Custom document properties'}[low]
                    for element in _xml(content).iter():
                        key, value = _local(element.tag), (element.text or '').strip()
                        if value and key not in SKIP_METADATA:
                            parts.append(_part('metadata', f'{label}: "{key}"', f'{key}: {value}'))
                elif re.fullmatch(r'word/(header|footer)\d*\.xml', low):
                    kind = 'header' if 'header' in low else 'footer'
                    parts.append(_part(kind, f'Page {kind} ({Path(name).stem})', _paragraphs(_xml(content))))
                elif re.fullmatch(r'word/comments\w*\.xml', low):
                    parts.append(_part('comment', 'Reviewer comments', _paragraphs(_xml(content))))
                elif low in {'word/footnotes.xml', 'word/endnotes.xml'}:
                    parts.append(_part('footnote', 'Footnotes' if 'foot' in low else 'Endnotes', _paragraphs(_xml(content))))
                elif low.startswith('word/glossary/') and low.endswith('.xml'):
                    parts.append(_part('glossary', 'Building blocks / glossary', _paragraphs(_xml(content))))
                elif low == 'word/document.xml':
                    root = _xml(content)
                    extra, deleted, fields, alt = [], [], [], []
                    for element in root.iter():
                        tag = _local(element.tag)
                        if tag == 'p':
                            text = ''.join(t.text or '' for t in element.iter() if _local(t.tag) == 't')
                            if text.strip() and re.sub(r'\s+', ' ', text).strip() not in body:
                                extra.append(text)
                        elif tag == 'delText' and (element.text or '').strip():
                            deleted.append(element.text)
                        elif tag == 'instrText' and (element.text or '').strip():
                            fields.append(element.text)
                        elif tag == 'docPr':
                            alt += [element.get(k) for k in ('descr', 'title') if element.get(k)]
                    if extra:
                        parts.append(_part('unrendered', 'Text outside the main body (text boxes, tracked insertions, content controls)', '\n'.join(extra)))
                    if deleted:
                        parts.append(_part('tracked_change', 'Tracked deletions', '\n'.join(deleted)))
                    if fields:
                        parts.append(_part('field_code', 'Field codes', '\n'.join(fields)))
                    if alt:
                        parts.append(_part('alt_text', 'Image alt text', '\n'.join(alt)))
                elif low.endswith('.rels'):
                    targets = [e.get('Target') for e in _xml(content).iter()
                               if e.get('TargetMode') == 'External' and e.get('Target')]
                    if targets:
                        parts.append(_part('link', 'External link targets', '\n'.join(targets)))
                elif low.startswith('word/embeddings/'):
                    parts += _embedded_parts(Path(name).name, content, 'attachment', None, ocr)
                elif low.startswith('word/media/') and Path(low).suffix in IMAGE_SUFFIXES and ocr:
                    parts.append(_part('image_text', f'Text in image {Path(name).name} (OCR)', _ocr_image(content, Path(low).suffix)))
            except ElementTree.ParseError as exc:
                parts.append(_part('unreadable', name, f'[{name} could not be parsed: {exc}]',
                                   forced=f'{name} could not be parsed, so it cannot be verified as safe.'))
    return parts


def load_pages(path, ocr=False):
    return load_parts(path, ocr)[0]


def load_parts(path, ocr=False):
    """Visible text (pages) plus every hidden channel (hidden parts) of a document."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in SUPPORTED:
        raise ValueError(f'Unsupported file type: {path.suffix}')
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Document exceeds the 20 MB limit')
    data = path.read_bytes()
    suffix = path.suffix.lower()
    pages, hidden = [], []
    if suffix in {'.txt', '.md'}:
        pages = [{'page': None, 'section': 'Text', 'text': data.decode('utf-8-sig', errors='replace')}]
    elif suffix == '.pdf':
        pages, hidden = _pdf_parts(data, ocr)
    else:
        document = Document(BytesIO(data))
        section = 'Document'
        # Preserve paragraphs and tables in original document order.
        for block in document.iter_inner_content():
            if hasattr(block, 'text'):
                if block.style and block.style.name.startswith('Heading'):
                    section = block.text
                pages.append({'page': None, 'section': section, 'text': block.text})
            else:
                pages.append({'page': None, 'section': section,
                    'text': '\n'.join(' | '.join(c.text for c in row.cells) for row in block.rows)})
        checkpoint('Inspecting properties, comments, headers and embedded content')
        hidden = _docx_hidden(data, '\n'.join(p['text'] for p in pages), ocr)
    # Invisible Unicode is decoded into its own hidden part, then removed from the visible text.
    for page in pages:
        payload = invisible_payload(page['text'])
        if payload.strip():
            hidden.append(_part('invisible_text', f"Invisible Unicode text in {page.get('section') or 'text'}", payload, page.get('page')))
        page['text'] = clean_text(page['text'])
    hidden = [h for h in hidden if h['text'] or h['forced']]
    if sum(len(h['text']) for h in hidden) > MAX_HIDDEN_CHARS:
        raise ValueError('Hidden document content (metadata, comments, attachments) is too large to inspect safely.')
    if sum(len(p['text']) for p in pages) > MAX_TEXT_CHARS:
        raise ValueError('Extracted text exceeds the 2 million character limit.')
    if not any(p['text'].strip() for p in pages):
        raise ValueError('No extractable text found.')
    return pages, hidden


def load_document(path):
    return '\n\n'.join(p['text'] for p in load_pages(path))


def chunk_text(text, size=1500, overlap=250):
    if size <= overlap or overlap < 0:
        raise ValueError('Chunk size must exceed overlap')
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            breaks = list(re.finditer(r'\n\s*\n|(?<=[.!?])\s+|\n', text[start:end]))
            suitable = [m.end() for m in breaks if m.end() > size // 2]
            if suitable:
                end = start + suitable[-1]
        part = text[start:end].strip()
        if part:
            chunks.append(part)
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap)
        # Avoid splitting the word at the start of the overlap.
        while next_start < end and not text[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


def document_chunks(pages):
    chunks = []
    for page in pages:
        for text in chunk_text(page['text']):
            chunks.append({**page, 'text': text, 'chunk_index': len(chunks)})
    return chunks
