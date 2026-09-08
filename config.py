"""Unified secret/config loading for local .env and Streamlit Cloud.

Precedence:
1. Streamlit secrets (including common sectioned forms)
2. Process environment
3. Optional default supplied by the caller

This module intentionally exposes only configuration values and does not
participate in retrieval, ranking, calculations, fallback data, or tracing.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from typing import Any


def _streamlit_value(name: str) -> str | None:
    """Read a secret from st.secrets without requiring Streamlit at import time."""
    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        return None

    # Root-level TOML: OPENAI_API_KEY = "..."
    candidates = [name, name.lower()]
    for key in candidates:
        try:
            value = secrets.get(key)
            if value not in (None, ""):
                return str(value).strip()
        except Exception:
            pass

    # Common sectioned TOML forms:
    # [openai] api_key = "..."
    # [tavily] api_key = "..."
    # [alphavantage] api_key = "..."
    base = name.removesuffix("_API_KEY").lower()
    section_candidates = [base]
    if base == "alphavantage":
        section_candidates += ["alpha_vantage", "alpha-vantage"]

    key_candidates = ["api_key", "API_KEY", name.lower(), name]
    for section in section_candidates:
        try:
            block = secrets.get(section)
        except Exception:
            block = None
        if isinstance(block, Mapping):
            for key in key_candidates:
                try:
                    value = block.get(key)
                except Exception:
                    value = None
                if value not in (None, ""):
                    return str(value).strip()

    return None


def get_setting(name: str, default: Any = None) -> Any:
    """Get a configuration value, preferring Streamlit Cloud secrets."""
    value = _streamlit_value(name)
    if value not in (None, ""):
        return value
    value = os.getenv(name)
    if value not in (None, ""):
        return str(value).strip()
    return default


def load_runtime_environment() -> dict[str, str]:
    """Resolve provider/API settings and mirror them into os.environ.

    Existing application modules read os.environ, so mirroring resolved
    Streamlit secrets here lets the working research engine remain unchanged.
    No secret values are logged or displayed by this module.
    """
    names = (
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "ALPHAVANTAGE_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_TIMEOUT",
        "OPENAI_MAX_TOKENS",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "OLLAMA_TIMEOUT",
        "OLLAMA_CONNECT_TIMEOUT",
        "OLLAMA_NUM_PREDICT",
        "OLLAMA_NUM_CTX",
    )
    resolved: dict[str, str] = {}
    for name in names:
        value = get_setting(name)
        if value not in (None, ""):
            value = str(value).strip()
            resolved[name] = value
            os.environ[name] = value
    return resolved


def is_streamlit_cloud() -> bool:
    """Best-effort detection used only to avoid assuming local Ollama on Cloud."""
    markers = (
        "STREAMLIT_SHARING_MODE",
        "IS_STREAMLIT_CLOUD",
        "STREAMLIT_CLOUD",
    )
    if any(os.getenv(k, "").strip().lower() in {"1", "true", "yes", "cloud"} for k in markers):
        return True
    # Best-effort request-host check; this is only used to avoid trying a
    # developer's localhost Ollama from a hosted Streamlit app.
    try:
        import streamlit as st
        host = str(st.context.headers.get("Host", "")).lower()
        if host.endswith(".streamlit.app") or host.endswith(".streamlit.cloud"):
            return True
    except Exception:
        pass
    return False


def secret_fingerprint() -> str:
    """Return a non-secret cache key that changes when provider credentials change."""
    values = []
    for name in ("OPENAI_API_KEY", "TAVILY_API_KEY", "ALPHAVANTAGE_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        value = get_setting(name, "")
        values.append(f"{name}={value}")
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()[:16]


def provider_status() -> dict[str, bool | str]:
    """Return safe, non-secret provider diagnostics for the UI."""
    resolved = load_runtime_environment()
    return {
        "cloud": is_streamlit_cloud(),
        "openai": bool(resolved.get("OPENAI_API_KEY")),
        "tavily": bool(resolved.get("TAVILY_API_KEY")),
        "alphavantage": bool(resolved.get("ALPHAVANTAGE_API_KEY")),
        "ollama_configured": bool(resolved.get("OLLAMA_BASE_URL") or resolved.get("OLLAMA_MODEL")),
    }
