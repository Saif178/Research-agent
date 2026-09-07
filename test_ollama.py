import os

from llm.ollama_client import OllamaClient


def test_default_timeout_is_bounded(monkeypatch):
    monkeypatch.delenv("OLLAMA_TIMEOUT", raising=False)
    client = OllamaClient(model="llama3.1")
    assert client.timeout == 60.0


def test_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT", "120")
    client = OllamaClient(model="llama3.1")
    assert client.timeout == 120.0
