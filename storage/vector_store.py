import os
from typing import List, Dict

class VectorStore:
    def __init__(self, backend=None, collection="financial_chunks"):
        self.backend = backend or os.getenv("VECTOR_BACKEND", "chroma").lower()
        self.collection_name = collection
        if self.backend == "chroma":
            import chromadb
            if os.getenv("CHROMA_HOST"):
                self.client = chromadb.HttpClient(host=os.getenv("CHROMA_HOST"), port=int(os.getenv("CHROMA_PORT", "8000")))
            elif os.getenv("CHROMA_API_KEY"):
                self.client = chromadb.CloudClient(tenant=os.getenv("CHROMA_TENANT"), database=os.getenv("CHROMA_DATABASE"), api_key=os.getenv("CHROMA_API_KEY"))
            else:
                self.client = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "./data/chroma"))
            self.collection = self.client.get_or_create_collection(collection)
        elif self.backend == "pgvector":
            from sqlalchemy import create_engine
            self.engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
            self._init_pg()
        else:
            raise ValueError("VECTOR_BACKEND must be chroma or pgvector")

    def _embed(self, texts):
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        return client.embeddings.create(model=model, input=texts).data

    def upsert(self, chunks):
        if not chunks: return
        if self.backend == "chroma":
            embs = [x.embedding for x in self._embed([c.text for c in chunks])]
            self.collection.upsert(
                ids=[c.chunk_id for c in chunks], documents=[c.text for c in chunks], embeddings=embs,
                metadatas=[{"source_id":c.source_id,"document_id":c.document_id,"page":c.page or -1, **c.metadata} for c in chunks])
        else:
            self._pg_upsert(chunks)

    def query(self, text, n=8, where=None):
        if self.backend == "chroma":
            emb = self._embed([text])[0].embedding
            r = self.collection.query(query_embeddings=[emb], n_results=n, where=where)
            out=[]
            for i, doc in enumerate(r.get("documents", [[]])[0]):
                out.append({"chunk_id":r["ids"][0][i],"text":doc,"metadata":r.get("metadatas",[[]])[0][i],"distance":r.get("distances",[[]])[0][i] if r.get("distances") else None})
            return out
        return self._pg_query(text,n,where)

    def _init_pg(self):
        from sqlalchemy import text
        with self.engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            c.execute(text("CREATE TABLE IF NOT EXISTS financial_chunks (chunk_id TEXT PRIMARY KEY, text TEXT NOT NULL, source_id TEXT, document_id TEXT, page INT, embedding vector(1536), metadata JSONB DEFAULT '{}'::jsonb)"))

    def _pg_upsert(self, chunks):
        from sqlalchemy import text
        embs = [x.embedding for x in self._embed([c.text for c in chunks])]
        with self.engine.begin() as c:
            for ch, emb in zip(chunks, embs):
                c.execute(text("""INSERT INTO financial_chunks(chunk_id,text,source_id,document_id,page,embedding,metadata) VALUES(:id,:text,:sid,:did,:page,:emb,:meta) ON CONFLICT(chunk_id) DO UPDATE SET text=EXCLUDED.text, embedding=EXCLUDED.embedding, metadata=EXCLUDED.metadata"""), {"id":ch.chunk_id,"text":ch.text,"sid":ch.source_id,"did":ch.document_id,"page":ch.page,"emb":str(emb),"meta":ch.metadata})

    def _pg_query(self,text_query,n,where):
        from sqlalchemy import text
        emb=self._embed([text_query])[0].embedding
        sql="SELECT chunk_id,text,source_id,document_id,page,metadata,1-(embedding <=> :emb) AS score FROM financial_chunks ORDER BY embedding <=> :emb LIMIT :n"
        with self.engine.begin() as c:
            rows=c.execute(text(sql),{"emb":str(emb),"n":n}).mappings().all()
        return [{"chunk_id":r["chunk_id"],"text":r["text"],"metadata":r["metadata"],"distance":1-r["score"]} for r in rows]
