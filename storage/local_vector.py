from pathlib import Path
from project_paths import CHROMA_DIR
import hashlib, os, re
import numpy as np
import chromadb
import requests

class LocalChromaStore:
    """Stable zero-API-key Chroma store.

    Default retrieval uses a deterministic local hashing embedding. This is
    intentionally the default for Streamlit ingestion because it performs no
    Ollama HTTP calls per PDF chunk and therefore avoids long blocking runs,
    timeouts, and websocket disconnects. Ollama embeddings remain optional.
    """
    def __init__(self, path=None, collection='financial_documents_v3'):
        path = str(path or CHROMA_DIR)
        Path(path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name=collection, metadata={'hnsw:space': 'cosine'}
        )
        self.fallback_dim = 384
        self.backend = os.getenv('EMBEDDING_BACKEND', 'local').lower().strip()
        self.ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
        self.embed_model = os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text')

    def _id(self, text, metadata):
        raw = text + '|' + str(sorted(metadata.items()))
        return hashlib.sha256(raw.encode()).hexdigest()

    def _hash_embedding(self, text):
        # Stable feature hashing: same fixed dimension for indexing and search.
        v = np.zeros(self.fallback_dim, dtype=np.float32)
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        for token in tokens:
            h = hashlib.blake2b(token.encode('utf-8'), digest_size=8).digest()
            idx = int.from_bytes(h[:4], 'little') % self.fallback_dim
            v[idx] += 1.0 if (h[4] & 1) else -1.0
        n = np.linalg.norm(v)
        if n:
            v /= n
        return v.tolist()

    def _ollama_embedding(self, text):
        r = requests.post(
            self.ollama_url + '/api/embeddings',
            json={'model': self.embed_model, 'prompt': text}, timeout=45
        )
        r.raise_for_status()
        emb = r.json().get('embedding')
        if not emb:
            raise RuntimeError('Ollama returned no embedding')
        return emb

    def _embedding(self, text):
        if self.backend == 'ollama':
            return self._ollama_embedding(text)
        return self._hash_embedding(text)

    def add(self, text, metadata):
        return self.add_many([text], [metadata])[0]

    def add_many(self, texts, metadatas, batch_size=128):
        ids = [self._id(t, m) for t, m in zip(texts, metadatas)]
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            bt, bm, bi = texts[start:end], metadatas[start:end], ids[start:end]
            embeddings = [self._embedding(t) for t in bt]
            self.collection.upsert(
                ids=bi, documents=bt, metadatas=bm, embeddings=embeddings
            )
        return ids

    def search(self, query, k=8, where=None):
        kw = {'query_embeddings': [self._embedding(query)], 'n_results': k}
        if where:
            kw['where'] = where
        return self.collection.query(**kw)

    def count(self):
        return self.collection.count()
