# 07_full_application

Independent Financial GraphRAG package.

This ZIP is a standalone, extractable package—not a split archive fragment.

Runtime data directories are intentionally empty. Place your offline annual-report PDFs in `annual_reports/` and run:

    python offline_ingest.py

Then launch the RAG UI (package 04 or 07):

    streamlit run app.py

See `README_OFFLINE_INGEST_RAG.md` for the full workflow.
