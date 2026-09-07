import json
from pathlib import Path
from project_paths import GRAPH_PATH
import networkx as nx

class LocalKnowledgeGraph:
    def __init__(self, path=None):
        self.path = Path(path or GRAPH_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = nx.MultiDiGraph()
        self.load()

    def load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                self.graph = nx.node_link_graph(data, directed=True, multigraph=True)
            except Exception:
                self.graph = nx.MultiDiGraph()

    def save(self):
        self.path.write_text(json.dumps(nx.node_link_data(self.graph), indent=2, default=str), encoding='utf-8')

    def add_entity(self, eid, name, label, **props):
        self.graph.add_node(eid, name=name, label=label, **props)

    def add_relation(self, sid, rel, tid, evidence_id=None, **props):
        if sid and tid:
            self.graph.add_edge(sid, tid, relation=rel, evidence_id=evidence_id, **props)

    def add_extraction(self, document_id, chunk_id, entities, relations, page=None):
        self.add_entity(chunk_id, chunk_id, 'EvidenceChunk', document_id=document_id, page=page)
        for e in entities:
            self.add_entity(e['id'], e['name'], e['type'], **e.get('metadata', {}))
            self.add_relation(e['id'], 'MENTIONED_IN', chunk_id, evidence_id=chunk_id)
        for sid, pred, tid, confidence in relations:
            self.add_relation(sid, pred, tid, evidence_id=chunk_id, confidence=confidence)

    def find_entities(self, text, limit=12):
        q = text.lower().strip()
        if not q:
            return []
        scored = []
        for nid, data in self.graph.nodes(data=True):
            if data.get('label') == 'EvidenceChunk':
                continue
            name = str(data.get('name', ''))
            n = name.lower()
            score = 2 if n == q else (1 if q in n or n in q else 0)
            if score:
                scored.append((score, nid, data))
        scored.sort(key=lambda x: (-x[0], str(x[2].get('name',''))))
        return [{'id': n, **d, '_score': s} for s, n, d in scored[:limit]]

    def multi_hop(self, entity_ids, hops=2, limit=50):
        found = {}
        for eid in entity_ids:
            if eid not in self.graph:
                continue
            for node, dist in nx.single_source_shortest_path_length(self.graph.to_undirected(), eid, cutoff=hops).items():
                if node != eid and node not in found:
                    found[node] = dist
        rows = []
        for node, dist in sorted(found.items(), key=lambda x: (x[1], str(self.graph.nodes[x[0]].get('name',''))))[:limit]:
            rows.append({'id': node, 'hop': dist, **self.graph.nodes[node]})
        return rows

    def evidence_for_entities(self, entity_ids, limit=50):
        out = []
        seen = set()
        for eid in entity_ids:
            if eid not in self.graph:
                continue
            for _, target, data in self.graph.out_edges(eid, data=True):
                if data.get('relation') == 'MENTIONED_IN' and target not in seen:
                    seen.add(target)
                    out.append({'id': target, **self.graph.nodes[target]})
            for source, _, data in self.graph.in_edges(eid, data=True):
                if data.get('relation') == 'MENTIONED_IN' and source not in seen:
                    seen.add(source)
                    out.append({'id': source, **self.graph.nodes[source]})
        return out[:limit]

    def relations_for(self, entity_ids, limit=100):
        rows = []
        ids = set(entity_ids)
        for sid in ids:
            if sid not in self.graph:
                continue
            for _, tid, d in self.graph.out_edges(sid, data=True):
                if d.get('relation') != 'MENTIONED_IN' and tid not in ids:
                    rows.append({'subject': self.graph.nodes[sid].get('name'), 'predicate': d.get('relation'), 'object': self.graph.nodes[tid].get('name'), 'confidence': d.get('confidence'), 'evidence_id': d.get('evidence_id')})
        return rows[:limit]

    def neighbors(self, eid, hops=2):
        return self.multi_hop([eid], hops=hops)

    def stats(self):
        labels = {}
        for _, d in self.graph.nodes(data=True):
            label = d.get('label', 'Unknown')
            labels[label] = labels.get(label, 0) + 1
        rels = {}
        for _, _, d in self.graph.edges(data=True):
            rel = d.get('relation', 'UNKNOWN')
            rels[rel] = rels.get(rel, 0) + 1
        return {'nodes': self.graph.number_of_nodes(), 'edges': self.graph.number_of_edges(), 'node_types': labels, 'relation_types': rels}
