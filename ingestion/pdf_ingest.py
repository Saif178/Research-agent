from pathlib import Path
from pypdf import PdfReader
from core.models import Source, Chunk, stable_id
from datetime import datetime, timezone

class AnnualReportIngestor:
    def __init__(self, vector_store, graph_store, llm):
        self.vector=vector_store; self.graph=graph_store; self.llm=llm
    def ingest(self,path,company="",year=""):
        path=Path(path); reader=PdfReader(str(path)); chunks=[]; sources=[]
        document_id=stable_id(str(path.resolve()),company,year)
        for page_no,page in enumerate(reader.pages,1):
            text=page.extract_text() or ""
            if not text.strip(): continue
            for idx,part in enumerate(self._chunk(text,1800,250)):
                sid=stable_id(document_id,str(page_no),str(idx))
                source=Source(source_id=sid,title=path.name,url="",publisher=company,source_type="annual_report",retrieved_at=datetime.now(timezone.utc).isoformat(),page=page_no,metadata={"year":year})
                chunks.append(Chunk(sid,part,sid,document_id,page_no,metadata={"company":company,"year":year,"source_type":"annual_report"})); sources.append(source)
        self.vector.upsert(chunks)
        self._extract_graph(chunks,company)
        return {"document_id":document_id,"pages":len(reader.pages),"chunks":len(chunks)}
    def _chunk(self,text,size,overlap):
        out=[]; start=0
        while start<len(text): out.append(text[start:start+size]); start += size-overlap
        return out
    def _extract_graph(self,chunks,company):
        from core.extraction import extract_graph
        entities=[]; relations=[]
        for ch in chunks:
            e,r=extract_graph(self.llm,ch.text,company,ch.chunk_id); entities.extend(e); relations.extend(r)
        self.graph.upsert_entities(entities); self.graph.upsert_relations(relations)
