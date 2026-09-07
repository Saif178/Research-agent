from pathlib import Path
import hashlib, re, os, gc, json
from pypdf import PdfReader
from core.local_graph_extractor import extract_fast

class LocalAnnualReportIngestor:
    """Crash-resistant, resumable local annual-report ingestion.

    Key design: process one page at a time, flush vectors/graph immediately,
    checkpoint the graph after each report, and skip reports already indexed.
    This prevents a large first PDF from keeping Streamlit busy with a giant
    in-memory payload before the next document can start.
    """
    def __init__(self, vector_store, graph, chunk_chars=2200, overlap=250, llm=None, llm_max_chunks=0, checkpoint_pages=5):
        self.vector = vector_store
        self.graph = graph
        self.chunk_chars = int(chunk_chars)
        self.overlap = int(overlap)
        self.llm = llm
        self.llm_max_chunks = int(llm_max_chunks or os.getenv('GRAPH_LLM_MAX_CHUNKS', '0'))
        self.checkpoint_pages = max(1, int(checkpoint_pages or os.getenv('GRAPH_CHECKPOINT_PAGES', '5')))

    def _chunks(self, text):
        step = max(1, self.chunk_chars - self.overlap)
        for start in range(0, len(text), step):
            chunk = text[start:start + self.chunk_chars].strip()
            if chunk:
                yield chunk

    def _document_id(self, p):
        # Include file size + mtime so replacing a PDF creates a new document id.
        st = p.stat()
        raw = f'{p.resolve()}|{st.st_size}|{st.st_mtime_ns}'
        return 'doc_' + hashlib.sha1(raw.encode()).hexdigest()[:16]

    def _already_ingested(self, doc_id):
        return self.graph.graph.has_node(doc_id) and self.graph.graph.nodes[doc_id].get('ingestion_complete') is True

    def _ollama_extract(self, text, company, chunk_id):
        if not self.llm:
            return [], []
        prompt = f'''Extract only facts explicitly supported by this annual-report passage. Return JSON only:
{{"entities":[{{"name":"...","type":"Company|Person|Product|Market|Regulation|Metric|Geography|Competitor|Technology"}}],"relations":[{{"subject":"...","predicate":"...","object":"...","confidence":0.0}}]}}
Company: {company}
Passage:\n{text}'''
        try:
            raw = self.llm.chat(prompt, system='You extract conservative financial knowledge graph facts. Never guess.', temperature=0)
            m = re.search(r'\{.*\}', raw, re.S)
            data = json.loads(m.group(0)) if m else {}
            ents, rels, lookup = [], [], {}
            from core.models import stable_id
            for x in data.get('entities', []):
                name = str(x.get('name','')).strip(); typ = str(x.get('type','')).strip()
                if name and typ:
                    eid = stable_id(typ, name.lower()); lookup[name.lower()] = eid
                    ents.append({'id': eid, 'name': name, 'type': typ, 'metadata': {'extraction':'ollama'}})
            for x in data.get('relations', []):
                s = lookup.get(str(x.get('subject','')).lower()); o = lookup.get(str(x.get('object','')).lower())
                if s and o:
                    try: conf = float(x.get('confidence', .7))
                    except Exception: conf = .7
                    rels.append((s, str(x.get('predicate','RELATED_TO')), o, conf))
            return ents, rels
        except Exception:
            return [], []

    def ingest_pdf(self, pdf_path, company=None, year=None, progress=None, report_index=None, report_total=None):
        p = Path(pdf_path)
        reader = PdfReader(str(p))
        company = company or p.stem
        doc_id = self._document_id(p)
        if self._already_ingested(doc_id):
            if progress: progress(1.0, f'Skipped already-ingested report: {p.name}')
            return {'document_id':doc_id,'company':company,'year':year,'pages':len(reader.pages),'chunks':0,'status':'skipped','file':str(p)}

        company_id = 'company_' + hashlib.sha1(company.lower().encode()).hexdigest()[:16]
        self.graph.add_entity(doc_id, p.name, 'Document', company=company, year=year, path=str(p), ingestion_complete=False)
        self.graph.add_entity(company_id, company, 'Company')
        self.graph.add_relation(company_id, 'HAS_DOCUMENT', doc_id, evidence_id=doc_id)
        self.graph.save()  # checkpoint before expensive work

        page_count = len(reader.pages); total_chunks = 0; graph_nodes = 0; llm_done = 0
        for page_no, page in enumerate(reader.pages, 1):
            try:
                text = (page.extract_text() or '').strip()
            except Exception as exc:
                if progress: progress(page_no/max(page_count,1), f'Warning: could not extract page {page_no}: {exc}')
                continue
            if not text:
                continue

            page_texts=[]; page_metas=[]; page_payload=[]
            for chunk_no, chunk in enumerate(self._chunks(text)):
                evidence_id=f'{doc_id}_p{page_no}_c{chunk_no}'
                meta={'document_id':doc_id,'company':str(company),'year':str(year or ''),'page':str(page_no),'evidence_id':evidence_id,'source':p.name}
                page_texts.append(chunk); page_metas.append(meta)
                ents, rels = extract_fast(chunk, company, evidence_id)
                for e in ents:
                    if e['type']=='Company': e['id']=company_id
                page_payload.append((evidence_id, page_no, ents, rels, chunk))

            if page_texts:
                self.vector.add_many(page_texts, page_metas, batch_size=64)
                for evidence_id, pg, ents, rels, chunk in page_payload:
                    self.graph.add_extraction(doc_id, evidence_id, ents, rels, page=pg)
                    graph_nodes += len(ents)
                    if self.llm and self.llm_max_chunks > llm_done:
                        e2,r2=self._ollama_extract(chunk, company, evidence_id)
                        self.graph.add_extraction(doc_id, evidence_id, e2, r2, page=pg)
                        llm_done += 1
                total_chunks += len(page_texts)

            # Persist periodically. Vector data is already durable; graph checkpoints
            # are intentionally batched because serializing a large NetworkX graph to
            # JSON on every page can itself become the dominant bottleneck.
            self.graph.graph.nodes[doc_id]['pages_processed'] = page_no
            self.graph.graph.nodes[doc_id]['chunks_processed'] = total_chunks
            if page_no % self.checkpoint_pages == 0 or page_no == page_count:
                self.graph.save()
            if progress:
                base=(report_index-1)/report_total if report_index and report_total else 0
                span=1/report_total if report_index and report_total else 1
                progress(min(0.99, base + span*(page_no/page_count)),
                         f'Ingesting {p.name} — page {page_no}/{page_count}, {total_chunks} chunks')
            del page_texts, page_metas, page_payload
            gc.collect()

        self.graph.graph.nodes[doc_id]['ingestion_complete']=True
        self.graph.graph.nodes[doc_id]['pages_processed']=page_count
        self.graph.graph.nodes[doc_id]['chunks_processed']=total_chunks
        self.graph.save()
        if progress: progress(1.0 if not report_index else report_index/report_total, f'Completed {p.name}: {total_chunks} chunks')
        return {'document_id':doc_id,'company':company,'year':year,'pages':page_count,'chunks':total_chunks,'graph_nodes_added':graph_nodes,'llm_chunks':llm_done,'status':'ok','file':str(p)}

    def ingest_directory(self, directory='data/annual_reports', progress=None):
        root=Path(directory)
        if not root.exists(): return [{'status':'error','error':f'Directory not found: {root}'}]
        pdfs=sorted(root.rglob('*.pdf'))
        if not pdfs: return [{'status':'empty','message':f'No PDF files found in {root}'}]
        out=[]; total=len(pdfs)
        for idx,p in enumerate(pdfs,1):
            try:
                m=re.search(r'(20\d{2})',p.stem)
                out.append(self.ingest_pdf(p,year=int(m.group(1)) if m else None,progress=progress,report_index=idx,report_total=total))
            except Exception as exc:
                # Continue to the next PDF instead of terminating the batch.
                out.append({'status':'error','file':str(p),'error':repr(exc)})
                if progress: progress(idx/total, f'Error in {p.name}; continuing with report {idx+1}/{total}')
        if progress: progress(1.0,f'Finished batch: {len(pdfs)} report(s)')
        return out
