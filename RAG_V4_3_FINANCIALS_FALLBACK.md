# RAG v4.3 — Annual Reports + Financials Dataset Fallback

The research pipeline now uses a two-tier evidence policy:

1. **Annual reports (`[E#]`) are primary evidence.**
2. If a requested financial metric is not established by the retrieved annual-report passages, the pipeline queries the supplied `data/financials` CSV/XLSX/XLS/JSON dataset and can cite those rows as **`[F#]`**.
3. The model must never represent `[F#]` data as if it came from an annual report.
4. No values are calculated, interpolated, estimated, or filled from model knowledge.
5. If neither source establishes the requested value, the model must say:
   **“Not established by the retrieved evidence.”**

The financials dataset is read at query time, so users can replace/add datasets in `data/financials` without rebuilding ChromaDB.
