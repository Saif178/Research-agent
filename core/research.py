import os, json, re, math
from datetime import datetime, timezone
from core.models import Source, Chunk, Evidence, stable_id
from core.calculations import calculate_from_evidence
from providers.market_data import AlphaVantageProvider, SECProvider

SYSTEM = '''You are a strictly evidence-grounded financial research analyst.
SOURCE PRIORITY: official/company/regulatory websites and supplied financial APIs first; other reputable websites second; local financial dataset only when web evidence does not establish the requested value.
Never use uploaded annual-report/Chroma evidence as a source for this website-first mode.
Every factual financial claim must cite [W#] or [F#]. Calculated results must cite every input source and show the formula briefly.
Never invent, estimate, interpolate, or silently repair missing numbers. If the evidence does not establish a requested fact or calculation, write exactly: Not established by the retrieved evidence.
Distinguish reported values from calculated values. Flag conflicting web sources instead of choosing silently.'''

class ResearchEngine:
    def __init__(self,llm,vector=None,graph=None,web_search=None,max_steps=None):
        self.llm,self.vector,self.graph,self.web=llm,vector,graph,web_search
        from ingestion.local_financials import LocalFinancialData
        from project_paths import FINANCIALS_DIR
        self.financials=LocalFinancialData()
        self.financials_dir=FINANCIALS_DIR
        self.market=AlphaVantageProvider(); self.sec=SECProvider()
        self.max_steps=int(max_steps or os.getenv('MAX_RESEARCH_STEPS','8'))
        self.min_steps=int(os.getenv('MIN_RESEARCH_STEPS','3'))
        self.max_web_results=int(os.getenv('MAX_WEB_RESULTS','8'))
        self.max_evidence=int(os.getenv('MAX_WEB_EVIDENCE','40'))

    def plan(self,query):
        # Deterministic plan: research planning must never require an LLM.
        q=query.lower()
        metrics=[]
        for label,terms in {
            'revenue growth':['revenue growth','sales growth','yoy growth'],
            'gross margin':['gross margin','gross profit margin'],
            'operating margin':['operating margin','ebit margin','operating profit margin'],
            'free cash flow margin':['free cash flow margin','fcf margin','free cash flow / sales'],
            'debt to equity':['debt to equity','debt/equity'],
            'cagr':['cagr','compound annual growth'],
        }.items():
            if any(t in q for t in terms): metrics.append(label)
        entities=[]
        known={'tcs':'TCS','infosys':'INFOSYS','cipla':'CIPLA','sun pharma':'SUNPHARMA','sun pharmaceutical':'SUNPHARMA'}
        for name,symbol in known.items():
            if name in q: entities.append({'name':name,'symbol':symbol})
        return {'query':query,'entities':entities,'questions':[query],
                'required_financial_metrics':metrics,'calculation_requirements':metrics,
                'primary_web_sources':['official investor relations','SEC/BSE/NSE/regulatory filings','reputable financial websites'],
                'verification_targets':[],'source_mode':'website_first'}

    def run(self,query,plan,progress=None):
        evidence=[]; seen=set(); actions=[]; unresolved=list(plan.get('questions') or [query])
        # Structured APIs are website-hosted financial data and are allowed as primary evidence.
        for ent in plan.get('entities',[]):
            symbol=ent.get('symbol') if isinstance(ent,dict) else None
            if not symbol: continue
            for kind,fn in [('overview',self.market.overview),('income_statement',self.market.income_statement),('balance_sheet',self.market.balance_sheet),('cash_flow',self.market.cash_flow)]:
                try:
                    data=fn(symbol)
                    if isinstance(data,dict) and 'error' not in data:
                        sid=stable_id('alphavantage',symbol,kind)
                        src=Source(sid,f'Alpha Vantage {kind}: {symbol}','https://www.alphavantage.co/documentation/','Alpha Vantage','financial_api',datetime.now(timezone.utc).isoformat())
                        text=json.dumps(data,ensure_ascii=False)
                        evidence.append(Evidence(Chunk(stable_id(sid,text[:120]),text,sid,sid,metadata={'symbol':symbol,'metric_type':kind}),src,score=1.0))
                except Exception: pass

        for step in range(1,self.max_steps+1):
            q=self._next_query(query,plan,evidence,unresolved,step)
            if not q: break
            if progress: progress(step,q)
            try: raw=self.web.search(q,self.max_web_results)
            except Exception as exc:
                actions.append({'step':step,'query':q,'error':f'{type(exc).__name__}: {exc}'})
                raw=[]
            new=0
            for r in raw:
                url=r.get('url','').strip(); text=(r.get('text') or '').strip()
                if not url or not text: continue
                sid=stable_id(url)
                if sid in seen: continue
                seen.add(sid); new+=1
                src=Source(sid,r.get('title',''),url,r.get('publisher','web'),'web',datetime.now(timezone.utc).isoformat(),r.get('published_at',''))
                ch=Chunk(stable_id(sid,text[:160]),text,sid,sid,metadata={'query':q,'web_source':True})
                # Official/company/regulatory domains get a ranking bonus.
                bonus=0.35 if any(x in url.lower() for x in ['sec.gov','company','investor','bseindia','nseindia','moneycontrol','reuters','economictimes']) else 0
                evidence.append(Evidence(ch,src,score=float(r.get('score') or 0)+bonus))
            actions.append({'step':step,'query':q,'new_web_sources':new,'total_web_evidence':len(evidence)})
            if new==0 and not unresolved and step>=self.min_steps: break
            if len(evidence)>=self.max_evidence: break
            if unresolved: unresolved.pop(0)
        # Secondary fallback: only query the supplied financials dataset when web/API evidence is weak.
        web_evidence_count=len(evidence)
        if web_evidence_count < 4 or any(k in query.lower() for k in ['calculate','growth','margin','cagr','debt to equity','free cash flow']):
            try:
                rows=self.financials.search(query,directory=str(self.financials_dir),top_k=6)
                for i,row in enumerate(rows):
                    text=row.get('text','')
                    sid=stable_id('financials',row.get('source',''),text)
                    src=Source(sid,row.get('source','Financials dataset'),'','Supplied financials dataset','financials_dataset',datetime.now(timezone.utc).isoformat())
                    ch=Chunk(stable_id(sid,text[:120]),text,sid,sid,metadata={'financials_fallback':True})
                    evidence.append(Evidence(ch,src,score=float(row.get('retrieval_score') or 0)))
                actions.append({'step':'fallback','query':query,'financial_dataset_sources':len(rows) if 'rows' in locals() else 0,'web_evidence_before_fallback':web_evidence_count})
            except Exception as exc:
                actions.append({'step':'fallback','query':query,'financial_dataset_sources':0,'error':f'{type(exc).__name__}: {exc}'})
        ranked=self._rank(query,evidence)
        selected=ranked[:8]
        return self.synthesize(query,plan,selected,actions)

    def _next_query(self,query,plan,evidence,unresolved,step):
        # Deterministic query expansion avoids an extra LLM call during retrieval.
        if unresolved:
            unresolved.pop(0)
            return query
        metrics=' '.join(plan.get('required_financial_metrics',[]))
        expansions=[
            query + ' official investor relations financial results',
            query + ' revenue profit operating margin cash flow',
            query + ' annual financial results investor presentation',
            query + ' regulatory filing financial statements',
        ]
        return expansions[min(max(step-1,0),len(expansions)-1)]

    def _rank(self,query,evidence):
        terms=set(re.findall(r'[a-z0-9]{3,}',query.lower()))
        ranked=[]
        for e in evidence:
            text=e.chunk.text.lower(); overlap=sum(1 for t in terms if t in text)/max(1,len(terms))
            source_bonus=0.25 if e.source.source_type=='financial_api' else 0
            official=0.2 if any(x in e.source.url.lower() for x in ['sec.gov','investor','bseindia','nseindia']) else 0
            ranked.append((e.score+overlap*0.8+source_bonus+official,e))
        ranked.sort(key=lambda x:x[0],reverse=True)
        return [e for _,e in ranked]

    def synthesize(self,query,plan,evidence,actions):
        blocks=[]
        for i,e in enumerate(evidence,1):
            tag=f'[W{i}]' if e.source.source_type in ('web','financial_api') else f'[F{i}]'
            text=e.chunk.text
            # Compact relevant excerpt; retain enough context for numerical calculations.
            excerpt=text[:900]
            blocks.append(f'{tag} TITLE: {e.source.title}\nURL: {e.source.url}\nEVIDENCE: {excerpt}')
        calc=calculate_from_evidence(query,'\n'.join(b for b in blocks))
        calc_hint=('Candidate calculations found from explicitly retrieved inputs: '+', '.join(f'{x:.4g}' for x in calc)) if calc else 'No deterministic calculation was produced by the local calculator; calculate only from explicitly cited inputs.'
        prompt=f'''Research question: {query}\nPlan: {json.dumps(plan,ensure_ascii=False)}\n{calc_hint}\n\nEvidence (use only this):\n{chr(10).join(blocks)}\n\nWrite a concise financial research answer. For every factual statement add [W#]/[F#]. For calculations, show formula, inputs, result, and citations. If a value/calculation is not established, say: Not established by the retrieved evidence. Do not cite or mention local uploaded annual reports.'''
        try: report=self.llm.complete(prompt,system=SYSTEM)
        except Exception as exc:
            report='## Evidence-only result\n\nSynthesis was unavailable. The following retrieved website/API evidence is available for manual verification.\n\n'+ '\n\n'.join(blocks) + f'\n\nGeneration error: {type(exc).__name__}: {exc}'
        report += '\n\n## Provenance\n' + '\n'.join(f'- [{"W" if s.source_type in ("web","financial_api") else "F"}] {s.title} | {s.url}' for s in [e.source for e in evidence])
        return {'report':report,'actions':actions,'sources':[e.source.__dict__ for e in evidence]}
