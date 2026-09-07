from pathlib import Path
import json
import os
import re
import heapq
import pandas as pd


class LocalFinancialData:
    """Bounded, query-time search over local financial datasets.

    This is a SECONDARY evidence source. It is intentionally defensive: files,
    sheets and rows are processed incrementally so a large/odd workbook cannot
    exhaust Streamlit memory. No calculations or interpolation are performed.
    """
    SUPPORTED = ('.csv', '.xlsx', '.xls', '.json')

    def __init__(self):
        self.max_files = int(os.getenv('FINANCIALS_MAX_FILES', '20'))
        self.max_sheets = int(os.getenv('FINANCIALS_MAX_SHEETS', '12'))
        self.max_rows_per_sheet = int(os.getenv('FINANCIALS_MAX_ROWS_PER_SHEET', '5000'))
        self.csv_chunk_rows = int(os.getenv('FINANCIALS_CSV_CHUNK_ROWS', '5000'))
        self.max_file_mb = float(os.getenv('FINANCIALS_MAX_FILE_MB', '75'))
        self.max_cells_per_frame = int(os.getenv('FINANCIALS_MAX_CELLS_PER_FRAME', '250000'))

    @staticmethod
    def _tokens(text):
        return set(re.findall(r'[a-z0-9]+', str(text).lower()))

    @staticmethod
    def _safe_value(v):
        if pd.isna(v):
            return None
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v

    def _score_frame(self, df, query, source_file, source_sheet, top_k):
        if df is None or df.empty:
            return []
        # Hard bound on frame width as well as rows.
        if len(df.columns) > 80:
            df = df.iloc[:, :80]
        max_rows = max(1, min(self.max_rows_per_sheet, self.max_cells_per_frame // max(1, len(df.columns))))
        df = df.head(max_rows)

        q_tokens = self._tokens(query)
        q_terms = [t for t in q_tokens if len(t) >= 3]
        if not q_tokens:
            return []

        out = []
        for idx, row in df.iterrows():
            vals = {}
            for k, v in row.items():
                if str(k).startswith('_'):
                    continue
                sv = self._safe_value(v)
                if sv is not None:
                    vals[str(k)] = sv
            if not vals:
                continue
            text = ' '.join(f'{k} {v}' for k, v in vals.items())
            lower = text.lower()
            tokens = self._tokens(lower)
            overlap = len(q_tokens & tokens) / max(1, len(q_tokens))
            hits = sum(1 for t in q_terms if t in lower)
            lexical = min(1.0, hits / max(1, min(len(q_terms), 10)))
            score = 0.65 * overlap + 0.35 * lexical
            if score <= 0:
                continue
            pairs = [f'{k}: {v}' for k, v in vals.items()]
            loc = f', sheet={source_sheet}' if source_sheet else ''
            out.append({
                'text': '; '.join(pairs),
                'source': f'Financials dataset — {source_file}{loc}',
                'source_type': 'financials_dataset',
                'row_index': int(idx) if isinstance(idx, int) else str(idx),
                'retrieval_score': round(score, 4),
            })
        out.sort(key=lambda x: -x['retrieval_score'])
        return out[:top_k]

    def _iter_file_frames(self, p):
        s = p.suffix.lower()
        if s == '.csv':
            # Chunked CSV avoids loading the whole dataset.
            for n, chunk in enumerate(pd.read_csv(p, chunksize=self.csv_chunk_rows)):
                yield chunk, f'chunk-{n+1}'
                if (n + 1) * self.csv_chunk_rows >= self.max_rows_per_sheet:
                    break
            return

        if s in ('.xlsx', '.xls'):
            book = pd.ExcelFile(p)
            for sheet in book.sheet_names[:self.max_sheets]:
                # nrows materially limits memory for wide/large workbooks.
                df = pd.read_excel(book, sheet_name=sheet, nrows=self.max_rows_per_sheet)
                yield df, str(sheet)
            return

        if s == '.json':
            # JSON is bounded after parsing; oversized files are rejected before this point.
            obj = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(obj, dict):
                obj = obj.get('data', obj)
            df = pd.DataFrame(obj).head(self.max_rows_per_sheet)
            yield df, None
            return

        raise ValueError(f'Unsupported format: {s}')

    def search(self, query, directory='data/financials', top_k=8):
        """Return top query-relevant dataset rows without concatenating all files.

        Failures are isolated per file/sheet. Only supplied values are surfaced.
        """
        root = Path(directory)
        if not root.exists():
            return []

        candidates = []
        files = [p for p in sorted(root.iterdir()) if p.is_file() and p.suffix.lower() in self.SUPPORTED]
        for p in files[:self.max_files]:
            try:
                mb = p.stat().st_size / (1024 * 1024)
                if mb > self.max_file_mb:
                    print(f'Skipping oversized financial dataset {p.name}: {mb:.1f} MB > {self.max_file_mb:.1f} MB')
                    continue
                for df, sheet in self._iter_file_frames(p):
                    candidates.extend(self._score_frame(df, query, p.name, sheet, top_k))
                    # Keep the candidate pool bounded after every frame.
                    candidates = heapq.nlargest(max(top_k * 4, 16), candidates, key=lambda x: x['retrieval_score'])
                    del df
            except Exception as e:
                print(f'Skipping financial dataset {p}: {type(e).__name__}: {e}')
                continue

        candidates.sort(key=lambda x: -x['retrieval_score'])
        return candidates[:top_k]
