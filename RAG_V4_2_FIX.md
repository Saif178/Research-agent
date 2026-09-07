# RAG v4.2 fallback fix

- Streamlit now loads the project `.env` before initializing RAG resources.
- `OPENAI_API_KEY` is detected for controlled synthesis fallback.
- Sidebar reports whether the OpenAI fallback is configured (never displays the key).
- Ollama remains dynamically model-discovered.
- Ollama failure -> OpenAI synthesis using the same evidence-only prompt -> evidence-only fallback.
