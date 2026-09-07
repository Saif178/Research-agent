# RAG v4 Optimization

The research pipeline is optimized for local Ollama synthesis:

1. Broad retrieval uses multiple query formulations.
2. Hybrid ranking combines semantic distance, lexical overlap, term density, and primary-source quality.
3. Duplicate and near-duplicate passages are removed without collapsing distinct chunks from the same source.
4. Only the top 8–10 evidence passages are sent to Ollama.
5. Each passage is reduced to a query-focused excerpt (default 1,400 characters).
6. NetworkX graph data is used for retrieval/navigation only and is not injected into the synthesis prompt.
7. Every factual claim must carry an `[E#]` citation.
8. Unsupported claims must use: `Not established by the retrieved evidence.`
9. Ollama model discovery uses `/api/tags`; `OLLAMA_MODEL` is optional.
10. If synthesis fails, the application returns an evidence-only report and explicitly states that no unsupported conclusions were generated.

Environment variables:

- `OLLAMA_BASE_URL` — default `http://localhost:11434`
- `OLLAMA_MODEL` — optional override; otherwise the first installed model is discovered
- `OLLAMA_TIMEOUT` — generation timeout, default 60 seconds
- `OLLAMA_CONNECT_TIMEOUT` — API connection timeout, default 3 seconds


## V4.1 inference hardening
- Final synthesis is limited to 8 passages and ~800-character relevant excerpts.
- Ollama generation is bounded with `num_predict=450` and `num_ctx=4096`.
- The installed model remains dynamically discovered from `/api/tags`.
- If `OPENAI_API_KEY` is configured, OpenAI is a controlled fallback using the identical evidence-only prompt.
- If both generators fail, the application returns evidence-only output and does not invent conclusions.
