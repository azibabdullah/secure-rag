from pathlib import Path
from unittest.mock import Mock
import pytest
from tests.test_document_routing import pipeline
from tests.test_security_reliability import store
from src.utils.operations import CancelledError


def application(tmp_path, monkeypatch, enabled):
    monkeypatch.setattr('src.rag.pipeline.load_settings', lambda: {'screen_documents_on_upload': enabled})
    app = pipeline([])
    app.store = store(tmp_path / 'profile')
    return app


def document(tmp_path, text, name='sample.txt'):
    path = tmp_path / name
    path.write_text(text, encoding='utf-8')
    return str(path.resolve())


def test_deferred_upload_then_retrieval_blocks_poison(tmp_path, monkeypatch):
    app = application(tmp_path, monkeypatch, False)
    path = document(tmp_path, 'POISON instructions')
    result = app.ingest(path)
    app.classifier.score.assert_not_called()
    assert result['status'] == 'DEFERRED'
    assert result['approved_chunks'] == 0
    assert app.store.source_chunks(path)[0]['decision'] == 'DEFERRED'
    response = app.ask('Summarize', 'documents', path)
    assert response['status'] == 'WITHHELD'  # explains which passage was blocked and why
    assert response['withheld'][0]['stage'] == 'retrieval' and 'scored 0.990' in response['withheld'][0]['reason']
    app.llm.answer_documents.assert_not_called()
    panel = app.document_decision(path)
    assert 'disabled' in panel['rows'][0]['reason']
    assert panel['rows'][0]['retrieval_check']['decision'] == 'BLOCKED'
    app.store.close()


def test_deferred_upload_allows_benign_after_retrieval_check(tmp_path, monkeypatch):
    app = application(tmp_path, monkeypatch, False)
    path = document(tmp_path, 'The observatory opens at 09:30.')
    app.ingest(path)
    response = app.ask('When does it open?', 'documents', path)
    assert response['status'] == 'ANSWERED'
    assert '09:30' in app.llm.answer_documents.call_args.args[1]
    assert app.document_decision(path)['rows'][0]['retrieval_check']['decision'] == 'SAFE'
    app.store.close()


def test_guarded_upload_keeps_poison_out_of_index_and_explains_score(tmp_path, monkeypatch):
    app = application(tmp_path, monkeypatch, True)
    path = document(tmp_path, 'POISON instructions')
    result = app.ingest(path)
    assert result['status'] == 'QUARANTINED' and result['indexed_chunks'] == 0
    assert app.store.source_chunks(path) == []
    row = app.document_decision(path)['rows'][0]
    assert '0.990000' in row['reason'] and 'at or above' in row['reason']
    assert '0.500' in row['reason']
    app.store.close()


def test_reupload_changes_mode_without_reusing_old_decision(tmp_path, monkeypatch):
    app = application(tmp_path, monkeypatch, True)
    path = document(tmp_path, 'POISON')
    app.ingest(path)
    monkeypatch.setattr('src.rag.pipeline.load_settings', lambda: {'screen_documents_on_upload': False})
    app.ingest(path)
    assert app.store.documents()[0]['status'] == 'DEFERRED'
    assert app.store.source_chunks(path)
    monkeypatch.setattr('src.rag.pipeline.load_settings', lambda: {'screen_documents_on_upload': True})
    app.ingest(path)
    assert app.store.source_chunks(path) == []
    app.store.close()


def test_failed_batch_file_does_not_prevent_later_files():
    app = pipeline([])
    app.ingest = Mock(side_effect=[{'source': 'a'}, ValueError('broken PDF'), {'source': 'c'}])
    result = app.ingest_many(['a', 'b', 'c'])
    assert len(result['files']) == 3
    assert result['files'][1]['error'] == 'broken PDF'
    assert result['files'][2]['result']['source'] == 'c'


def test_cancel_batch_keeps_completed_results():
    app = pipeline([])
    app.ingest = Mock(side_effect=[{'source': 'a'}, CancelledError()])
    result = app.ingest_many(['a', 'b', 'c'])
    assert result['cancelled'] and result['remaining'] == ['b', 'c']
    assert len(result['files']) == 1
