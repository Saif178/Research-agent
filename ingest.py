import argparse
from dotenv import load_dotenv
load_dotenv()
from core.llm import LLM
from storage.vector_store import VectorStore
from storage.graph_store import GraphStore
from ingestion.pdf_ingest import AnnualReportIngestor
p=argparse.ArgumentParser(); p.add_argument('pdf'); p.add_argument('--company',default=''); p.add_argument('--year',default=''); a=p.parse_args()
print(AnnualReportIngestor(VectorStore(),GraphStore(),LLM()).ingest(a.pdf,a.company,a.year))
