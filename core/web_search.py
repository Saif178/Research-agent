import os, requests
class TavilySearch:
    def __init__(self): self.key=os.getenv('TAVILY_API_KEY')
    def search(self,q,n=10):
        if not self.key: return []
        r=requests.post('https://api.tavily.com/search',json={'api_key':self.key,'query':q,'search_depth':'advanced','max_results':n,'include_answer':False},timeout=30); r.raise_for_status()
        return [{'title':x.get('title',''),'url':x.get('url',''),'text':x.get('content',''),'score':x.get('score',0),'publisher':'web','source_type':'web'} for x in r.json().get('results',[])]
