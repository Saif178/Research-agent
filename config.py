"""Minimal runtime configuration for Streamlit Cloud and local development.

Source of truth:
- Streamlit secrets (``st.secrets``) when available.
- Local ``.env`` is loaded only for non-Cloud/local execution.

The rest of the application historically reads configuration from ``os.environ``.
This module resolves secrets once from ``st.secrets`` and mirrors only the resolved
values into the environment for backwards compatibility. No retrieval/RAG logic
is implemented here.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any


def is_streamlit_cloud() -> bool:
    """Best-effort detection of Streamlit Community Cloud."""
    for key in ("STREAMLIT_SHARING_MODE", "IS_STREAMLIT_CLOUD", "STREAMLIT_CLOUD"):
        value = os.getenv(key, "").strip().lower()
        if value in {"1", "true", "yes", "cloud"}:
            return True

    try:
        import streamlit as st
        headers = getattr(st.context, "headers", {})
        host = str(headers.get("Host", "")).lower()
        return ".streamlit.app" in host or ".streamlit.cloud" in host
    except Exception:
        return False


def _streamlit_secrets() -> Any:
    """Return st.secrets, or None when Streamlit/local secrets are unavailable."""
    try:
        import streamlit as st
        return st.secrets
    except Exception:
        return None


def _read_streamlit_secret(name: str, default: Any = None) -> Any:
    """Read only the requested root-level key from st.secrets.

    The application intentionally uses a simple root-level TOML contract. This
    avoids the previous over-engineered recursive/section discovery behavior.
    """
    secrets = _streamlit_secrets()
    if secrets is None:
        return default
    try:
        value = secrets.get(name)
    except Exception:
        return default
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    return value


def load_runtime_environment() -> dict[str, str]:
    """Load local .env only when not on Cloud, then resolve st.secrets first.

    ``st.secrets`` is authoritative whenever the requested key exists. The
    environment mirror exists only so existing clients can continue using their
    established ``os.getenv`` interfaces without changing research behavior.
    """
    if not is_streamlit_cloud():
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
        except Exception:
            pass

    names = (
        "OPENAI_API_KEY", "TAVILY_API_KEY", "ALPHAVANTAGE_API_KEY",
        "OPENAI_MODEL", "OPENAI_TIMEOUT", "OPENAI_MAX_TOKENS",
        "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT",
        "OLLAMA_CONNECT_TIMEOUT", "OLLAMA_NUM_PREDICT", "OLLAMA_NUM_CTX",
    )

    resolved: dict[str, str] = {}
    for name in names:
        # st.secrets is the only credential source. For local execution, .env
        # is the explicit fallback when a key is absent from st.secrets.
        secret_value = _read_streamlit_secret(name)
        if secret_value is not None:
            value = str(secret_value).strip()
        elif not is_streamlit_cloud():
            env_value = os.getenv(name)
            value = str(env_value).strip() if env_value not in (None, "") else ""
        else:
            value = ""

        if value:
            resolved[name] = value
            # Compatibility bridge for existing clients. Do not let a local
            # environment value override a value explicitly supplied in st.secrets.
            os.environ[name] = value

    return resolved


def get_setting(name: str, default: Any = None) -> Any:
    """Return a setting using st.secrets first and local .env second."""
    resolved = load_runtime_environment()
    return resolved.get(name, default)


def secret_sources() -> dict[str, str]:
    """Safe diagnostics; never returns credential values."""
    cloud = is_streamlit_cloud()
    out: dict[str, str] = {}
    for name in (
        "OPENAI_API_KEY", "TAVILY_API_KEY", "ALPHAVANTAGE_API_KEY",
        "OLLAMA_BASE_URL", "OLLAMA_MODEL",
    ):
        if _read_streamlit_secret(name) not in (None, ""):
            out[name] = "st.secrets"
        elif not cloud and os.getenv(name):
            out[name] = ".env / environment"
        else:
            out[name] = "not configured"
    return out


def secret_fingerprint() -> str:
    """Non-secret cache key that changes when configured providers change."""
    resolved = load_runtime_environment()
    names = (
        "OPENAI_API_KEY", "TAVILY_API_KEY", "ALPHAVANTAGE_API_KEY",
        "OPENAI_MODEL", "OLLAMA_BASE_URL", "OLLAMA_MODEL",
    )
    values = [f"{name}={resolved.get(name, '')}" for name in names]
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()[:16]


def provider_status() -> dict[str, bool | str]:
    """Safe provider diagnostics for the sidebar."""
    resolved = load_runtime_environment()
    return {
        "cloud": is_streamlit_cloud(),
        "openai": bool(resolved.get("OPENAI_API_KEY")),
        "tavily": bool(resolved.get("TAVILY_API_KEY")),
        "alphavantage": bool(resolved.get("ALPHAVANTAGE_API_KEY")),
        "ollama_configured": bool(
            resolved.get("OLLAMA_BASE_URL") or resolved.get("OLLAMA_MODEL")
        ),
    }
