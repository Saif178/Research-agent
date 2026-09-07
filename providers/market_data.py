import os, requests

class AlphaVantageProvider:
    BASE="https://www.alphavantage.co/query"
    def __init__(self,key=None): self.key=key or os.getenv("ALPHAVANTAGE_API_KEY")
    def call(self,function,**params):
        if not self.key: return {"error":"ALPHAVANTAGE_API_KEY not configured"}
        p={"function":function,"apikey":self.key,**params}
        r=requests.get(self.BASE,params=p,timeout=30); r.raise_for_status(); return r.json()
    def overview(self,symbol): return self.call("OVERVIEW",symbol=symbol)
    def income_statement(self,symbol): return self.call("INCOME_STATEMENT",symbol=symbol)
    def balance_sheet(self,symbol): return self.call("BALANCE_SHEET",symbol=symbol)
    def cash_flow(self,symbol): return self.call("CASH_FLOW",symbol=symbol)
    def quote(self,symbol): return self.call("GLOBAL_QUOTE",symbol=symbol)
    def news(self,tickers): return self.call("NEWS_SENTIMENT",tickers=tickers,limit=20)

class SECProvider:
    BASE="https://data.sec.gov"
    def __init__(self,user_agent=None): self.ua=user_agent or os.getenv("SEC_USER_AGENT","FinancialGraphRAG research@example.com")
    def _get(self,path):
        r=requests.get(self.BASE+path,headers={"User-Agent":self.ua},timeout=30); r.raise_for_status(); return r.json()
    def submissions(self,cik): return self._get(f"/submissions/CIK{int(cik):010d}.json")
    def companyfacts(self,cik): return self._get(f"/api/xbrl/companyfacts/CIK{int(cik):010d}.json")
