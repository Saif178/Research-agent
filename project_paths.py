from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ANNUAL_REPORTS_DIR = DATA_DIR / "annual_reports"
FINANCIALS_DIR = DATA_DIR / "financials"
CHROMA_DIR = DATA_DIR / "chroma"
GRAPH_PATH = DATA_DIR / "graph.json"

for _p in (DATA_DIR, ANNUAL_REPORTS_DIR, FINANCIALS_DIR, CHROMA_DIR):
    _p.mkdir(parents=True, exist_ok=True)
