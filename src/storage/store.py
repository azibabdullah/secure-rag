import hashlib
from uuid import uuid4

import chromadb
from sentence_transformers import SentenceTransformer

from src.storage.vault import Vault
from src.utils.app_paths import EMBEDDING_MODEL, user_data_dir
from src.utils.operations import checkpoint


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class VectorStore:
    def __init__(self, vault=None, encoder=None, client=None):
        self.vault = vault or Vault()
        if encoder is None and not EMBEDDING_MODEL.is_dir():
            raise FileNotFoundError(f'Bundled embedding model is missing: {EMBEDDING_MODEL}')
        self.encoder = encoder or SentenceTransformer(str(EMBEDDING_MODEL), device='cpu', local_files_only=True)
        self.client = client or chromadb.PersistentClient(path=str(user_data_dir() / 'chroma'),
            settings=chromadb.Settings(anonymized_telemetry=False))
        # Chroma contains vectors and opaque generation IDs, never chunk text.
        self.collection = self.client.get_or_create_collection(
            name='securerag_v3', embedding_function=None, metadata={'hnsw:space': 'cosine'})
        self.legacy_present = any(c.name == 'securerag_v2' for c in self.client.list_collections())

    def documents(self):
        return self.vault.all('document')

    def close(self):
        self.client.close()

    def duplicate(self, content_hash, source):
        return next((d for d in self.documents() if d.get('content_hash') == content_hash and d['source'] != source), None)

    def replace_source(self, source, chunks, *, result=None, content_hash=None):
        generation = uuid4().hex
        rows = []
        for item in chunks:
            row = dict(item) if isinstance(item, dict) else {'chunk_index': item[0], 'text': item[1], 'decision': 'SAFE'}
            row.update(id=f"{generation}:{row['chunk_index']}", source=source, sha256=text_hash(row['text']), similarity=None)
            rows.append(row)
        approved = [r for r in rows if r.get('decision', 'SAFE') in {'SAFE', 'DEFERRED'}]
        # Publish only after every vector is staged. Old data remains usable on failure.
        try:
            for start in range(0, len(approved), 32):
                checkpoint(f'Indexing excerpts {start + 1}-{min(start + 32, len(approved))} of {len(approved)}')
                batch = approved[start:start + 32]
                vectors = self.encoder.encode([r['text'] for r in batch], normalize_embeddings=True).tolist()
                self.collection.add(ids=[r['id'] for r in batch], embeddings=vectors,
                                    metadatas=[{'generation': generation} for _ in batch])
            checkpoint('Saving encrypted document')
            record = {'source': source, 'generation': generation, 'chunks': rows, 'content_hash': content_hash,
                      'status': 'SAFE', 'indexed_chunks': len(approved), 'quarantined_chunks': len(rows)-len(approved), **(result or {})}
            old = self.vault.get('document', self.vault.identity(source))
            self.vault.put('document', self.vault.identity(source), record)
        except Exception:
            self.collection.delete(where={'generation': generation})
            raise
        if old:
            try:
                self.collection.delete(where={'generation': old['generation']})
            except Exception:
                pass  # Orphans are filtered by the committed manifest on every read.

    def preview(self, source):
        document = self.vault.get('document', self.vault.identity(source))
        return document['chunks'] if document else []

    def source_chunks(self, source):
        return sorted([r for r in self.preview(source) if r.get('decision', 'SAFE') in {'SAFE', 'DEFERRED'}], key=lambda r: r['chunk_index'])

    def record_retrieval_check(self, hit, decision, score=None):
        from datetime import datetime, timezone
        ident = self.vault.identity(hit['source'])
        document = self.vault.get('document', ident)
        if not document:
            return
        for row in document['chunks']:
            if row['id'] == hit['id']:
                row['retrieval_check'] = {'decision': decision, 'score': score,
                    'time': datetime.now(timezone.utc).isoformat()}
                self.vault.put('document', ident, document)
                break

    def document(self, source):
        return self.vault.get('document', self.vault.identity(source))

    def retrieve(self, question, limit=4, min_similarity=0.35, source=None):
        scope = None if not source else ({source} if isinstance(source, str) else set(source))
        documents = [d for d in self.documents() if (scope is None or d['source'] in scope) and d['indexed_chunks']]
        if not documents:
            return []
        rows = {r['id']: r for d in documents for r in d['chunks'] if r.get('decision', 'SAFE') in {'SAFE', 'DEFERRED'}}
        if not rows:
            return []
        vector = self.encoder.encode([question], normalize_embeddings=True).tolist()
        result = self.collection.query(query_embeddings=vector, n_results=min(len(rows), max(limit*4, limit)),
            where={'generation': {'$in': [d['generation'] for d in documents]}}, include=['distances'])
        hits = []
        for ident, distance in zip(result['ids'][0], result['distances'][0]):
            similarity = 1 - float(distance)
            if ident in rows and similarity >= min_similarity:
                hits.append({**rows[ident], 'similarity': similarity})
        return hits

    def delete_source(self, source):
        old = self.vault.get('document', self.vault.identity(source))
        self.vault.delete('document', self.vault.identity(source))
        if old:
            self.collection.delete(where={'generation': old['generation']})

    def import_legacy(self):
        if not self.legacy_present:
            return 0
        old = self.client.get_collection('securerag_v2', embedding_function=None).get(include=['documents', 'metadatas'])
        grouped = {}
        for text, meta in zip(old['documents'], old['metadatas']):
            if text_hash(text) != meta['sha256']:
                raise RuntimeError('Legacy document hash mismatch; migration stopped.')
            grouped.setdefault(meta['source'], []).append((meta['chunk_index'], text))
        for source, chunks in grouped.items():
            if self.vault.get('document', self.vault.identity(source)) is None:
                self.replace_source(source, chunks)
        return len(grouped)
