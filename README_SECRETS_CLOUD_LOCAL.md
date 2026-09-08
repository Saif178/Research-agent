# Secrets: Streamlit Cloud and Local Development

The application now uses **`st.secrets` as the single source of truth for secrets**.
The local `.env` file is retained only as a non-Cloud fallback for developers who do
not use `.streamlit/secrets.toml`.

## Local development — recommended

Create:

```text
.streamlit/secrets.toml
```

using:

```toml
OPENAI_API_KEY = "..."
TAVILY_API_KEY = "..."
ALPHAVANTAGE_API_KEY = "..."
OPENAI_MODEL = "gpt-4o-mini"
```

The application reads these values through `st.secrets`.

If a local `st.secrets` value is absent, the application may fall back to `.env`.
`.env` is never used as a Cloud fallback.

## Streamlit Community Cloud

Open the deployed app's **Manage app / Settings → Secrets** and paste the same
root-level TOML:

```toml
OPENAI_API_KEY = "..."
TAVILY_API_KEY = "..."
ALPHAVANTAGE_API_KEY = "..."
OPENAI_MODEL = "gpt-4o-mini"
```

The app reads these values through `st.secrets`. No `.env` file is required or
expected on Cloud.

## Provider selection

1. OpenAI when `OPENAI_API_KEY` is configured in `st.secrets`.
2. On local/self-hosted execution only, Ollama may be used when OpenAI is absent
   and Ollama is reachable/configured.
3. On Cloud, localhost Ollama is never assumed. A reachable remote Ollama endpoint
   must be explicitly configured.
4. If no synthesis provider is available, the application remains in evidence-only
   mode.

Tavily and Alpha Vantage are independently detected and do not determine the
synthesis-provider choice.

## Security

Do **not** commit `.streamlit/secrets.toml` or `.env`.
The repository contains only `.streamlit/secrets.toml.example` as a template.
