import sqlite3, json, os
from core.models import Entity, Relation

class GraphStore:
    def __init__(self, path=None):
        self.path=path or os.getenv("GRAPH_DB","./data/graph.sqlite")
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.db=sqlite3.connect(self.path, check_same_thread=False)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS entities(entity_id TEXT PRIMARY KEY,name TEXT,entity_type TEXT,aliases TEXT,metadata TEXT);
        CREATE TABLE IF NOT EXISTS relations(relation_id TEXT PRIMARY KEY,subject_id TEXT,predicate TEXT,object_id TEXT,source_id TEXT,confidence REAL,evidence_chunk_id TEXT);
        CREATE INDEX IF NOT EXISTS idx_rel_sub ON relations(subject_id); CREATE INDEX IF NOT EXISTS idx_rel_obj ON relations(object_id);''')
        self.db.commit()
    def upsert_entities(self, entities):
        for e in entities:
            self.db.execute("INSERT OR REPLACE INTO entities VALUES(?,?,?,?,?)",(e.entity_id,e.name,e.entity_type,json.dumps(e.aliases),json.dumps(e.metadata)))
        self.db.commit()
    def upsert_relations(self, rels):
        for r in rels:
            self.db.execute("INSERT OR REPLACE INTO relations VALUES(?,?,?,?,?,?,?)",(r.relation_id,r.subject_id,r.predicate,r.object_id,r.source_id,r.confidence,r.evidence_chunk_id))
        self.db.commit()
    def find_entities(self, names):
        q=" OR ".join(["lower(name)=lower(?)"]*len(names))
        if not names: return []
        rows=self.db.execute(f"SELECT * FROM entities WHERE {q}",names).fetchall()
        return [self._entity(r) for r in rows]
    def neighbors(self, entity_ids, hops=2):
        seen=set(entity_ids); frontier=set(entity_ids); edges=[]
        for _ in range(hops):
            if not frontier: break
            marks=','.join('?'*len(frontier)); params=list(frontier)+list(frontier)
            rows=self.db.execute(f"SELECT * FROM relations WHERE subject_id IN ({marks}) OR object_id IN ({marks})",params).fetchall()
            nxt=set()
            for r in rows:
                rel=self._relation(r); edges.append(rel)
                other=rel.object_id if rel.subject_id in frontier else rel.subject_id
                if other not in seen: nxt.add(other); seen.add(other)
            frontier=nxt
        return list(seen), edges
    def _entity(self,r): return Entity(r[0],r[1],r[2],json.loads(r[3] or '[]'),json.loads(r[4] or '{}'))
    def _relation(self,r): return Relation(*r)
