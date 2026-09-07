"""Offline annual-report ingestion for Financial GraphRAG.

Run this script from a terminal BEFORE starting Streamlit.

Examples
--------
python offline_ingest.py
python offline_ingest.py --directory "D:/Annual Reports"
python offline_ingest.py --reset
python offline_ingest.py --llm-enrich --max-llm 20

The script builds/persists:
    data/chroma/
    data/graph.json

Streamlit only reads those persisted stores for RAG research.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

from project_paths import ANNUAL_REPORTS_DIR, CHROMA_DIR, GRAPH_PATH
from ingestion.local_reports import LocalAnnualReportIngestor
from storage.local_vector import LocalChromaStore
from storage.local_graph import LocalKnowledgeGraph


def parse_args():
    p = argparse.ArgumentParser(description="Offline annual-report ingestion into ChromaDB + NetworkX.")
    p.add_argument(
        "--directory",
        default=str(ANNUAL_REPORTS_DIR),
        help="Directory containing annual-report PDFs."
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing Chroma store and graph before ingestion."
    )
    p.add_argument(
        "--llm-enrich",
        action="store_true",
        help="Optionally enrich a bounded number of chunks using Ollama."
    )
    p.add_argument(
        "--max-llm",
        type=int,
        default=20,
        help="Maximum chunks per run for Ollama graph enrichment."
    )
    p.add_argument(
        "--checkpoint-pages",
        type=int,
        default=10,
        help="Persist graph every N processed PDF pages."
    )
    return p.parse_args()


def reset_stores():
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR, ignore_errors=False)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    if GRAPH_PATH.exists():
        GRAPH_PATH.unlink()


def main():
    args = parse_args()
    report_dir = Path(args.directory).expanduser().resolve()

    print("=" * 78)
    print("FINANCIAL GRAPHRAG — OFFLINE ANNUAL REPORT INGESTION")
    print("=" * 78)
    print(f"Reports directory : {report_dir}")
    print(f"Chroma store      : {CHROMA_DIR}")
    print(f"Graph store       : {GRAPH_PATH}")
    print(f"Embedding backend : {os.getenv('EMBEDDING_BACKEND', 'local')}")
    print(f"Ollama enrichment : {'ON' if args.llm_enrich else 'OFF'}")
    print()

    if not report_dir.exists():
        raise SystemExit(f"Annual-report directory does not exist: {report_dir}")

    pdfs = sorted(report_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF files found in: {report_dir}")

    if args.reset:
        print("Resetting existing Chroma and graph stores...")
        reset_stores()

    vector = LocalChromaStore()
    graph = LocalKnowledgeGraph()

    llm = None
    if args.llm_enrich:
        from llm.ollama_client import OllamaClient
        llm = OllamaClient()

    ingestor = LocalAnnualReportIngestor(
        vector_store=vector,
        graph=graph,
        llm=llm,
        llm_max_chunks=max(0, args.max_llm if args.llm_enrich else 0),
        checkpoint_pages=max(1, args.checkpoint_pages),
    )

    last_line_len = 0

    def progress(pct, msg):
        nonlocal last_line_len
        pct = max(0.0, min(1.0, float(pct)))
        line = f"[{pct*100:6.2f}%] {msg}"
        padding = " " * max(0, last_line_len - len(line))
        print("\r" + line + padding, end="", flush=True)
        last_line_len = len(line)

    start = time.time()
    print(f"Found {len(pdfs)} PDF(s). Starting offline ingestion...\n")

    try:
        results = ingestor.ingest_directory(str(report_dir), progress=progress)
        print("\n")
    except KeyboardInterrupt:
        print("\nIngestion interrupted by user. Persisted checkpoints remain available.")
        raise SystemExit(130)

    graph.save()

    elapsed = time.time() - start
    completed = sum(1 for x in results if x.get("status") == "complete")
    skipped = sum(1 for x in results if x.get("status") == "skipped")
    errors = [x for x in results if x.get("status") == "error"]

    print("-" * 78)
    print("INGESTION SUMMARY")
    print("-" * 78)
    for item in results:
        print(
            f"{item.get('status','unknown').upper():9s} | "
            f"{Path(item.get('file','')).name} | "
            f"pages={item.get('pages','-')} | chunks={item.get('chunks','-')}"
        )

    print()
    print(f"Completed        : {completed}")
    print(f"Skipped          : {skipped}")
    print(f"Errors           : {len(errors)}")
    print(f"Chroma documents : {vector.count()}")
    print(f"Graph nodes      : {graph.graph.number_of_nodes()}")
    print(f"Graph edges      : {graph.graph.number_of_edges()}")
    print(f"Elapsed seconds  : {elapsed:.1f}")
    print()
    print("Offline ingestion finished.")
    print("Now start the research UI with:")
    print("    streamlit run app.py")

    if errors:
        print("\nFiles with errors:")
        for e in errors:
            print(f"  - {Path(e.get('file','')).name}: {e.get('error','Unknown error')}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
