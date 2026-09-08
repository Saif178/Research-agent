# Secrets and Cloud/Local Provider Selection

This patch adds a single configuration layer without changing the website-first retrieval flow, financial dataset fallback, deterministic calculations, or Research Trace.

## Streamlit Community Cloud

In the app's **Settings → Secrets**, use either root-level keys:

```toml
OPENAI_API_KEY = "..."
TAVILY_API_KEY = "..."
ALPHAVANTAGE_API_KEY = "..."
OPENAI_MODEL = "gpt-4o-mini"
```

or the supported sectioned form:

```toml
[openai]
api_key = "..."

[tavily]
api_key = "..."

[alphavantage]
api_key = "..."
```

Root-level values take precedence over process environment values. The app resolves `st.secrets` first and mirrors resolved settings into the existing environment-based clients, so the research engine itself does not need to be rewritten.

After changing Cloud Secrets, restart/redeploy the app if the running instance has not picked up the new values.

## Local development

Use `.env` (never commit it) or normal environment variables. `.env.example` shows the expected names.

Provider selection is:

1. **OpenAI** when `OPENAI_API_KEY` is available.
2. **Ollama** locally when OpenAI is not configured and a reachable Ollama service/model is available.
3. **Evidence-only** when no synthesis provider is available.
4. On Streamlit Cloud, localhost Ollama is **not assumed**. A remote Ollama endpoint is used only when `OLLAMA_BASE_URL` or `OLLAMA_MODEL` is explicitly configured.

Tavily and Alpha Vantage are independently detected; they do not control the synthesis-provider choice.

## Security

The distribution no longer contains live API credentials in `.env`. If credentials that were present in an earlier package were real, rotate/revoke them before further use because they have been exposed in the package history.
