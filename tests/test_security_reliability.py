import json
from unittest.mock import Mock

import chromadb
import numpy as np
import pytest
import torch
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.security.classifier import InjectionClassifier, SecurityCheckError, validated_score
from src.security.output_guard import redact
from src.storage.vault import Vault, _dpapi
from src.storage.store import VectorStore
from src.storage.conversations import Conversations
from src.utils.operations import Operation, CancelledError, current_operation
from src.ingestion.loader import chunk_text, document_chunks
from tests.test_document_routing import pipeline, hit


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, 1.01])
def test_invalid_score_fails_closed(value):
    app = pipeline([hit()])
    app.classifier.classify.return_value = {'label': 'SAFE', 'score': value}
    with pytest.raises(SecurityCheckError):
        app.ask('hello')
    app.llm.answer_general.assert_not_called()


@pytest.mark.parametrize('logit', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_logits_never_become_safe(logit):
    classifier = InjectionClassifier.__new__(InjectionClassifier)
    classifier.device = torch.device('cpu')
    classifier._windows = lambda _: [{}]
    classifier.tokenizer = Mock()
    classifier.tokenizer.pad.return_value.to.return_value = {}
    classifier.model = Mock(return_value=Mock(logits=torch.tensor([[0.0, logit]])))
    with pytest.raises(SecurityCheckError):
        classifier.score(['anything'])


def test_aead_detects_changes_and_record_swaps(tmp_path):
    vault = Vault(tmp_path, AESGCM.generate_key(bit_length=256))
    vault.put('test', 'one', {'text': 'PRIVATE DOCUMENT CONTENT'})
    assert b'PRIVATE DOCUMENT CONTENT' not in vault.path.read_bytes()
    with vault.connect() as db:
        blob = db.execute('SELECT payload FROM records').fetchone()[0]
        db.execute('UPDATE records SET payload=?', (blob[:-1] + bytes([blob[-1] ^ 1]),))
    with pytest.raises(RuntimeError, match='authentication'):
        vault.get('test', 'one')
    with pytest.raises(RuntimeError, match='authentication'):
        vault.open('test:other', blob)


def test_dpapi_roundtrip():
    secret = AESGCM.generate_key(bit_length=256)
    assert _dpapi(_dpapi(secret), decrypt=True) == secret


class Encoder:
    fail = False
    def encode(self, texts, **kwargs):
        if self.fail:
            raise RuntimeError('simulated embedding failure')
        return np.array([[1.0, 0.0, 0.0] for _ in texts])


def store(tmp_path):
    return VectorStore(Vault(tmp_path, AESGCM.generate_key(bit_length=256)), Encoder(),
                       chromadb.PersistentClient(path=str(tmp_path / 'vectors')))


def test_atomic_reindex_quarantine_and_duplicate(tmp_path):
    database = store(tmp_path)
    database.replace_source('a.txt', [(0, 'old private content')], content_hash='original')
    database.encoder.fail = True
    with pytest.raises(RuntimeError):
        database.replace_source('a.txt', [(0, 'replacement')])
    assert database.source_chunks('a.txt')[0]['text'] == 'old private content'
    database.encoder.fail = False
    database.replace_source('a.txt', [dict(chunk_index=0, text='approved', decision='SAFE'),
                                    dict(chunk_index=1, text='poison', decision='QUARANTINED')], content_hash='new')
    assert len(database.preview('a.txt')) == 2
    assert [r['text'] for r in database.retrieve('question')] == ['approved']
    assert database.duplicate('new', 'other.txt')['source'] == 'a.txt'
    assert database.collection.get(include=['documents'])['documents'] == [None]


def test_cancel_preserves_old_generation(tmp_path):
    database = store(tmp_path)
    database.replace_source('a', [(0, 'original')])
    operation = Operation()
    operation.cancelled.set()
    token = current_operation.set(operation)
    try:
        with pytest.raises(CancelledError):
            database.replace_source('a', [(0, 'new')])
    finally:
        current_operation.reset(token)
    assert database.source_chunks('a')[0]['text'] == 'original'


def test_conversation_isolation_and_scope(tmp_path):
    conversations = Conversations(Vault(tmp_path, AESGCM.generate_key(bit_length=256)))
    a, b = conversations.create(), conversations.create()
    answer = {'status': 'ANSWERED', 'answer': 'A', 'sources': []}
    conversations.append(a['id'], 'What is the key length?', answer, 'documents', 'a.pdf')
    assert len(conversations.history(a['id'], 'documents', 'a.pdf')) == 1
    assert conversations.history(a['id'], 'documents', 'b.pdf') == []
    assert conversations.history(b['id'], 'documents', 'a.pdf') == []
    assert conversations.history(a['id'], 'chat', None) == []


def test_followup_uses_prior_user_topic_and_preserves_citations(tmp_path):
    app = pipeline([hit()])
    app.conversations = Conversations(Vault(tmp_path, AESGCM.generate_key(bit_length=256)))
    session = app.conversations.create()['id']
    app.llm.answer_documents.return_value = '56 bits [Excerpt 1]'
    app.ask('What is the key length?', 'documents', 'DES.pdf', session_id=session)
    result = app.ask('Explain it further', 'documents', 'DES.pdf', session_id=session)
    assert 'key length' in app.store.retrieve.call_args.args[0]
    assert result['sources'][0]['cited'] is True
    assert result['sources'][0]['text'] == hit()['text']


def test_invalid_citation_is_not_returned():
    app = pipeline([hit()])
    app.llm.answer_documents.return_value = 'Fact [Excerpt 999]'
    with pytest.raises(RuntimeError, match='citation'):
        app.ask('key length?', 'documents', 'DES.pdf')


def test_redaction_has_explicit_limited_scope():
    text, counts = redact('Email test@example.org; api_key=abcdefgh12345678; Bearer abcdefghijklmnopqrstuvwxyz')
    assert 'test@example.org' not in text
    assert 'abcdefgh12345678' not in text
    assert set(counts) == {'email', 'credential', 'bearer_token'}
    assert redact('DES uses a 56-bit key.')[0] == 'DES uses a 56-bit key.'


def test_chunking_keeps_late_text_and_page_provenance():
    pages = [{'page': 1, 'section': 'Opening', 'text': 'Normal sentence. ' * 200},
             {'page': 2, 'section': 'End', 'text': 'LATE PAYLOAD'}]
    rows = document_chunks(pages)
    assert rows[-1]['page'] == 2 and rows[-1]['text'] == 'LATE PAYLOAD'
    assert all(len(row['text']) <= 1500 for row in rows)
