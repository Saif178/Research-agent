import argparse, json
from dotenv import load_dotenv
load_dotenv()
from core.llm import LLM
from storage.vector_store import VectorStore
from storage.graph_store import GraphStore
from core.web_search import TavilySearch
from core.research import ResearchEngine

def main():
 p=argparse.ArgumentParser(); p.add_argument('query'); args=p.parse_args()
 llm=LLM(); eng=ResearchEngine(llm,VectorStore(),GraphStore(),TavilySearch())
 plan=eng.plan(args.query); print(json.dumps(plan,indent=2));
 if input('Approve plan? [y/N] ').lower()!='y': return
 out=eng.run(args.query,plan,lambda s,q: print(f'[{s}] {q}'))
 open('research_report.md','w',encoding='utf8').write(out['report']); print(out['report'])
if __name__=='__main__': main()
