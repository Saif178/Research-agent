# IMPORTANT — USE THE OFFLINE INGESTION WORKFLOW

For the current supported workflow, read `README_OFFLINE_INGEST_RAG.md`.
Annual reports are ingested with `python offline_ingest.py` before Streamlit starts.

# Financial GraphRAG — Zero API Key Edition

Fully local implementation: Ollama + local ChromaDB + NetworkX + local PDF/CSV/Excel/JSON data. No SEC, Alpha Vantage, PostgreSQL, PGVector, Neo4j Aura, OpenAI, OpenRouter or Tavily keys are required.

## Setup
1. Install Ollama and run `ollama pull llama3.1:8b`.
2. For embeddings, optionally install/use an Ollama embedding model; the included Chroma setup can also use its default embedding function if configured locally.
3. `python -m venv .venv`, activate it, then `pip install -r requirements.txt`.
4. Put annual reports in `data/annual_reports/` and financial CSV/XLSX/JSON in `data/financials/`.
5. Run `streamlit run app.py`.

## Architecture
Query → IT/Pharma router → plan/approval → local Chroma retrieval → NetworkX graph → broad retrieval → aggressive ranking → deduplication → compact top-10 evidence → Ollama synthesis → evidence-only fallback → trace dashboard.

## Data sovereignty
No network API is called by the application code. Ollama is expected at localhost. Annual reports and financial datasets are local files.

## vNext: True Local Financial GraphRAG

This release preserves the stable ingestion architecture and adds a real local knowledge-graph layer.

### Annual report pipeline

`PDF pages -> stable chunks -> Chroma batch indexing -> deterministic entity/metric extraction -> NetworkX entities/relations -> evidence provenance`

Every extracted graph fact is linked back to an evidence chunk, page, document and source filename. The deterministic extractor runs locally and does not call Ollama, so large reports do not create one LLM request per chunk.

### Optional Ollama graph enrichment

The Annual Reports tab includes an optional, bounded Ollama enrichment mode. Set a maximum number of chunks (default 20). This is intentionally capped to avoid the Streamlit disconnect problem caused by long-running per-chunk LLM calls.

### Research pipeline

The research agent now performs:

1. Query analysis and graph anchoring
2. Broad Chroma retrieval
3. Entity identification
4. 1–2 hop NetworkX expansion
5. Graph-guided retrieval queries
6. Financial evidence collection
7. Multi-step coverage/stagnation stopping
8. Ollama synthesis using both graph context and source passages

The graph is persisted in `data/graph.json`; vectors are persisted in `data/chroma`.

### Recommended first run

1. Delete the old `data/chroma` and `data/graph.json` if upgrading from an earlier package.
2. Put annual-report PDFs in `data/annual_reports`.
3. Keep `EMBEDDING_BACKEND=local` for stable ingestion.
4. Ingest reports with Ollama enrichment **off** first.
5. Confirm graph node/edge counts increase.
6. Run research queries.
7. Turn on bounded Ollama enrichment only when you want richer semantic entities.
