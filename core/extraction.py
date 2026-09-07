import json, re
from core.models import Entity, Relation, stable_id

def extract_graph(llm,text,company,chunk_id):
    prompt=f'''Extract financial knowledge graph facts from this annual-report passage. Return JSON only with entities and relations. Entity types: Company, Person, Product, Market, Regulation, Metric, Geography, Competitor, Technology. Relations should be factual and supported by the passage. Company context: {company}. Passage:\n{text}'''
    raw=llm.complete(prompt)
    try: data=json.loads(re.search(r'\{.*\}',raw,re.S).group(0))
    except Exception: return [],[]
    ents=[]
    for x in data.get('entities',[]):
        eid=stable_id(x.get('type',''),x.get('name','').lower())
        ents.append(Entity(eid,x.get('name',''),x.get('type',''),x.get('aliases',[]),{}))
    lookup={e.name.lower():e.entity_id for e in ents}
    rels=[]
    for x in data.get('relations',[]):
        s=lookup.get(x.get('subject','').lower()); o=lookup.get(x.get('object','').lower())
        if s and o:
            rels.append(Relation(stable_id(s,x.get('predicate',''),o,chunk_id),s,x.get('predicate',''),o,chunk_id,float(x.get('confidence',0.7)),chunk_id))
    return ents,rels
