# Financial GraphRAG — Offline Ingestion + Streamlit RAG

This version deliberately separates ingestion from the web application.

## Architecture

Annual report PDFs
→ `offline_ingest.py`
→ ChromaDB (`data/chroma`)
→ NetworkX graph (`data/graph.json`)
→ Streamlit
→ Graph-guided RAG
→ Ollama synthesis

Streamlit does **not** parse PDFs or write the annual-report vector/graph stores.

## 1. Install

```bat
pip install -r requirements.txt
```

Optional Ollama generation:

```bat
ollama pull llama3.1:8b
```

The stable retrieval default is the built-in deterministic local embedding backend,
so annual-report ingestion does not require ONNX Runtime or an embedding API.

## 2. Add annual reports

Copy PDFs to:

```text
data\annual_reports\
```

## 3. Build the index offline

```bat
python offline_ingest.py
```

Clean rebuild:

```bat
python offline_ingest.py --reset
```

Use another reports directory:

```bat
python offline_ingest.py --directory "D:\Annual Reports"
```

Optional bounded Ollama graph enrichment:

```bat
python offline_ingest.py --llm-enrich --max-llm 20
```

You can also double-click:

```text
ingest_annual_reports.bat
```

## 4. Start Streamlit only after ingestion finishes

```bat
streamlit run app.py
```

The Streamlit application opens the persisted Chroma/NetworkX stores for retrieval
and uses Ollama to synthesize the financial research report.

## Important

Do not run `offline_ingest.py` and Streamlit research against the same Chroma
store at the same time on Windows. Finish offline ingestion first, then launch
Streamlit.

If you add or replace reports later:

1. close Streamlit,
2. run `python offline_ingest.py`,
3. restart Streamlit.

Already-completed documents are resumable/skippable through the graph ingestion
metadata. Use `--reset` only when you intentionally want a clean rebuild.
