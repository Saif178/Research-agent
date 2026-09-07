# Financial GraphRAG — 07 Full Application (Corrected)

## Architecture

Offline ingestion is completely separate from Streamlit:

Annual-report PDFs -> `offline_ingest.py` -> ChromaDB + NetworkX graph -> Streamlit RAG

### Corrected startup behavior

The Streamlit app performs only lightweight filesystem checks during initial page load.
It does NOT:
- open ChromaDB at startup
- load the NetworkX graph at startup
- contact Ollama at startup
- load local financial datasets at startup

The UI therefore remains responsive even when ChromaDB, the graph, or Ollama is unavailable.

## Health diagnostics

The sidebar explicitly reports:
- Annual-report directory status
- ChromaDB directory status
- NetworkX graph file status
- Ollama status (not contacted until research)

Use **Detailed store health -> Check Chroma + Graph** for an explicit persisted-store check.

## Research workflow

1. Enter a financial query.
2. Create Research Plan.
3. Review the plan.
4. Explicitly approve the plan.
5. Click Approve & Run Research.
6. Only then are ChromaDB, NetworkX and Ollama initialized as needed.
7. Graph-guided retrieval and multi-step research execute.
8. Report and agent trace are displayed.

## Offline ingestion

Place annual-report PDFs in:

`data/annual_reports/`

Then run:

`python offline_ingest.py`

For a clean rebuild:

`python offline_ingest.py --reset`

The resulting stores are:

`data/chroma/`
`data/graph.json`

## Windows

Run:

`python -m streamlit run app.py`

or use:

`ingest_annual_reports.bat`

The project uses `Path(__file__).resolve()` so paths are independent of the current working directory.


## RAG grounding and ranking (v2)

The local RAG path now uses a compact, priority-ordered synthesis prompt. Retrieved chunks are ranked before synthesis using semantic similarity, query-term overlap, and a small primary-source preference for annual reports. The generator runs at temperature 0 and must attach `[E#]` evidence citations to factual claims, explicitly mark inference, report source conflicts, and state when a claim is not established. NetworkX graph relations are treated only as retrieval/navigation hints unless their linked evidence passage supports the claim.
