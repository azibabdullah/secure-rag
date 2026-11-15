from unittest.mock import Mock
import pytest
from src.rag.pipeline import SecureRAG
from src.storage.store import text_hash, VectorStore


def pipeline(rows):
    app = SecureRAG.__new__(SecureRAG)
    app.classifier = Mock(threshold=0.5)
    app.classifier.classify.return_value = {'label': 'SAFE', 'score': .01}
    app.classifier.score.side_effect = lambda texts: [.99 if 'POISON' in t else .01 for t in texts]
    app.doc_classifier = app.classifier  # DocumentGuard shares the mock so existing assertions hold
    app.store = Mock()
    app.store.source_chunks.return_value = rows
    app.store.retrieve.return_value = rows
    app.audit = Mock()
    app.llm = Mock()
    app.llm.answer_documents.return_value = 'A supported answer.'
    app.llm.answer_general.return_value = 'Hello.'
    return app


def hit(text='DES uses a 56-bit key.', index=0):
    return dict(id=str(index), text=text, sha256=text_hash(text),
                source='DES.pdf', chunk_index=index, similarity=.9)


def test_generic_question_uses_selected_document_without_similarity_filter():
    app = pipeline([hit()])
    answer = app.ask('What is this document about?', 'documents', 'DES.pdf')
    assert answer['status'] == 'ANSWERED'
    app.store.source_chunks.assert_called_once_with('DES.pdf')
    app.store.retrieve.assert_not_called()
    assert '56-bit' in app.llm.answer_documents.call_args.args[1]


def test_summary_requires_selection():
    app = pipeline([hit()])
    assert app.ask('Summarize this document', 'documents')['status'] == 'SELECT_DOCUMENT'
    app.llm.answer_documents.assert_not_called()


@pytest.mark.parametrize('rows', [[], [hit('POISON')], [{**hit(), 'sha256': 'tampered'}]])
def test_unusable_summary_context_never_reaches_llm(rows):
    app = pipeline(rows)
    # Empty or tampered context has nothing to explain; a poisoned passage is WITHHELD with its trail.
    assert app.ask('Summarize', 'documents', 'DES.pdf')['status'] == ('WITHHELD' if rows and rows[0]['text'] == 'POISON' and rows[0]['sha256'] != 'tampered' else 'NO_CONTEXT')
    app.llm.answer_documents.assert_not_called()


def test_topic_question_is_scoped_and_filtered():
    app = pipeline([hit()])
    app.ask('What is the key length?', 'documents', 'DES.pdf')
    app.store.retrieve.assert_called_once_with('What is the key length?', source='DES.pdf')


def test_blocked_prompt_never_reads_documents():
    app = pipeline([hit()])
    app.classifier.classify.return_value = {'label': 'MALICIOUS', 'score': .99}
    assert app.ask('Summarize', 'documents', 'DES.pdf')['status'] == 'BLOCKED'
    app.store.source_chunks.assert_not_called()
    app.llm.answer_documents.assert_not_called()


def test_long_overview_processes_all_excerpts():
    app = pipeline([hit(index=i) for i in range(12)])
    answer = app.ask('Summarize', 'documents', 'DES.pdf')
    assert '12 approved excerpts processed' in answer['answer']
    assert len(answer['sources']) == 12
    assert '[Excerpt 12]' in str(app.llm.answer_documents.call_args_list)


def test_source_chunks_order_and_scope():
    store = VectorStore.__new__(VectorStore)
    store.preview = Mock(return_value=[{'text': 'two', 'chunk_index': 2}, {'text': 'one', 'chunk_index': 1},
        {'text': 'POISON', 'chunk_index': 0, 'decision': 'QUARANTINED'}])
    assert [r['text'] for r in store.source_chunks('chosen.pdf')] == ['one', 'two']
    store.preview.assert_called_once_with('chosen.pdf')


def test_library_report_question_skips_promptguard_and_llm():
    app = pipeline([])
    app.store.documents.return_value = [
        {'source': 'S1.pdf', 'indexed_chunks': 1, 'quarantined_chunks': 0, 'chunks': [{'chunk_index': 0, 'score': .01, 'decision': 'SAFE'}]},
        {'source': 'P9.pdf', 'indexed_chunks': 0, 'quarantined_chunks': 1, 'chunks': [{'chunk_index': 0, 'score': .97, 'decision': 'QUARANTINED'}]}]
    result = app.ask('Give me report about all the documents that have been blocked and all that have been allowed', 'documents')
    assert result['status'] == 'REPORT'
    assert result['report']['counts']['Blocked'] == 1 and result['report']['counts']['Approved'] == 1
    app.classifier.classify.assert_not_called()
    app.llm.answer_documents.assert_not_called()
    app.llm.answer_general.assert_not_called()


def test_document_questions_still_go_through_promptguard():
    app = pipeline([hit()])
    app.ask('What does the policy say about blocked accounts?', 'documents', 'DES.pdf')
    app.classifier.classify.assert_called_once()


@pytest.mark.parametrize('question', ['Tell me all about these documents and what they do and what they represent',
                                      'Tell me about this document', 'What does this file contain?', 'Describe these documents',
                                      'Give me the key points', 'What are they about?'])
def test_whole_document_questions_read_every_approved_passage(question):
    app = pipeline([hit()])
    assert app.ask(question, 'documents', 'DES.pdf')['status'] == 'ANSWERED'
    app.store.source_chunks.assert_called_once_with('DES.pdf')


@pytest.mark.parametrize('question', ['What is the key length?', 'What does the policy say about blocked accounts?',
                                      'How much does AcmeSync cost?', 'Who owns the load test action item?'])
def test_specific_questions_still_use_similarity_search(question):
    from src.rag.pipeline import is_overview_question
    assert not is_overview_question(question)


def test_selected_document_is_used_even_when_nothing_is_similar():
    app = pipeline([hit()])
    app.store.retrieve.side_effect = lambda q, limit=4, min_similarity=0.35, source=None: [hit()] if min_similarity < 0 else []
    result = app.ask('Is anything here relevant to onboarding?', 'documents', 'DES.pdf')
    assert result['status'] == 'ANSWERED'
    assert '56-bit' in app.llm.answer_documents.call_args.args[1]


def test_overview_without_selection_covers_whole_small_library():
    app = pipeline([hit()])
    app.store.documents.return_value = [{'source': 'DES.pdf', 'indexed_chunks': 1, 'chunks': []},
                                        {'source': 'bad.pdf', 'indexed_chunks': 0, 'chunks': []}]
    assert app.ask('Summarize all documents', 'documents')['status'] == 'ANSWERED'
    assert [c.args[0] for c in app.store.source_chunks.call_args_list] == ['DES.pdf', 'bad.pdf']


def test_chat_question_about_my_documents_reads_the_library():
    app = pipeline([hit()])
    app.store.documents.return_value = [{'source': 'DES.pdf', 'indexed_chunks': 1, 'chunks': []}]
    result = app.ask('What are my documents about?', 'chat')
    assert result['status'] == 'ANSWERED' and result['used_documents']
    app.llm.answer_general.assert_not_called()
