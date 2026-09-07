# RAG v4.4 Stability Fix

The v4.3 financial-dataset fallback could reload every file/sheet, concatenate all rows, and scan the full combined frame for every research query. Large workbooks could therefore spike memory and crash Streamlit.

v4.4 changes the financial lookup to a bounded streaming design:
- no cross-file `pd.concat`;
- CSVs are read in chunks;
- Excel sheets are read with a row cap;
- file/sheet/row/cell limits are configurable by environment variables;
- oversized or malformed files are skipped independently instead of failing research;
- candidate evidence is pruned after each frame;
- `openai` and `python-dotenv` are explicitly declared dependencies.

Defaults:
- `FINANCIALS_MAX_FILES=20`
- `FINANCIALS_MAX_SHEETS=12`
- `FINANCIALS_MAX_ROWS_PER_SHEET=5000`
- `FINANCIALS_CSV_CHUNK_ROWS=5000`
- `FINANCIALS_MAX_FILE_MB=75`
- `FINANCIALS_MAX_CELLS_PER_FRAME=250000`

Evidence policy remains: annual reports `[E#]` first, supplied financial dataset `[F#]` second, otherwise `Not established by the retrieved evidence.`
