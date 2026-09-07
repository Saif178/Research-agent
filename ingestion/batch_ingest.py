from pathlib import Path
from ingestion.pdf_ingest import PDFIngestor
from graph.neo4j_store import Neo4jGraphStore

class AnnualReportBatchIngestor:
    def __init__(self, pdf_ingestor=None, graph=None):
        self.pdf = pdf_ingestor or PDFIngestor()
        self.graph = graph or Neo4jGraphStore()

    def ingest_directory(self, directory, company=None, year=None):
        directory = Path(directory)
        reports = sorted(directory.rglob("*.pdf"))
        results = []
        for pdf in reports:
            inferred_company = company or pdf.stem.split("_")[0]
            inferred_year = year or self._infer_year(pdf.stem)
            result = self.pdf.ingest(str(pdf), company=inferred_company, year=inferred_year)
            results.append({"file": str(pdf), "company": inferred_company,
                            "year": inferred_year, "result": result})
        return results

    @staticmethod
    def _infer_year(name):
        import re
        m = re.search(r"(20\d{2})", name)
        return int(m.group(1)) if m else None
