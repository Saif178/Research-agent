# Zero-API-Key Chroma fix

The previous runtime error occurs because Chroma's default embedding function uses ONNX MiniLM. On Windows/Python 3.12, the installed `onnxruntime` can fail with a native DLL initialization error.

This version fixes the problem at the application level:

- ChromaDB is still used locally.
- The app passes explicit embeddings to Chroma instead of allowing Chroma to load its default ONNX embedding function.
- Ollama `nomic-embed-text` is preferred for embeddings.
- If Ollama embedding is temporarily unavailable, a deterministic local hashing embedding is used so ingestion does not crash.
- The collection name is `financial_documents_v2`, avoiding incompatibility with a collection created using Chroma's old/default embedding function.

## Recommended clean restart

From the project directory:

```powershell
# Stop Streamlit with Ctrl+C

# Optional: remove only the old Chroma database if it was created by the previous version
Remove-Item -Recurse -Force .\data\chroma -ErrorAction SilentlyContinue

# Start Ollama and pull models
ollama pull llama3.1:8b
ollama pull nomic-embed-text

pip install -r requirements.txt
py -m streamlit run .\app.py
```

No SEC, Alpha Vantage, OpenAI, PostgreSQL, PGVector, Neo4j or Chroma Cloud key is required.
