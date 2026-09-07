# Stable Annual Report Ingestion Fix

The previous build could disconnect Streamlit while ingesting because every PDF chunk could trigger a separate Ollama embedding HTTP request. A large annual report can contain hundreds or thousands of chunks, so the Streamlit script remained blocked for a long time.

This build changes the default retrieval embedding backend to a deterministic local 384-dimensional feature-hash embedding. It requires **no Ollama call during ingestion**, batches Chroma upserts, shows page/report progress, and catches errors per PDF so one bad report does not terminate the app.

## Recommended reset

1. Stop Streamlit.
2. Delete the old `data/chroma` directory if it exists.
3. Keep `EMBEDDING_BACKEND=local` in `.env` (or omit it; local is the default).
4. Start Ollama only for the research-generation model if you want the LLM features.
5. Run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The Annual Reports tab now displays ingestion progress.

## Optional Ollama embeddings

If you explicitly want Ollama embeddings, set:

```text
EMBEDDING_BACKEND=ollama
OLLAMA_EMBED_MODEL=nomic-embed-text
```

and make sure the model is available in Ollama. Local mode is recommended for reliable demo ingestion.
