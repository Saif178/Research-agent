import hashlib
import re
import os
from llm.ollama_client import OllamaClient
from storage.local_vector import LocalChromaStore
from storage.local_graph import LocalKnowledgeGraph
from sectors.registry import route
from ingestion.local_financials import LocalFinancialData
from project_paths import FINANCIALS_DIR


class LocalFinancialGraphRAG:
    """Local financial GraphRAG with broad retrieval and compact evidence synthesis."""

    MAX_EVIDENCE = 8
    MAX_FINANCIAL_EVIDENCE = 4
    MIN_EVIDENCE = 6
    EXCERPT_CHARS = 800

    def __init__(self, max_steps=6):
        self.max_steps = max_steps
        self._llm = None
        self._vector = None
        self._graph = None
        self.trace = []

    @property
    def llm(self):
        if self._llm is None:
            # Model discovery is performed by OllamaClient from /api/tags.
            self._llm = OllamaClient()
        return self._llm

    @property
    def vector(self):
        if self._vector is None:
            self._vector = LocalChromaStore()
        return self._vector

    @property
    def graph(self):
        if self._graph is None:
            self._graph = LocalKnowledgeGraph()
        return self._graph

    def plan(self, q):
        return {
            'query': q,
            'sectors': route(q),
            'sources': ['annual reports', 'local CSV/XLSX/JSON', 'NetworkX knowledge graph', 'local ChromaDB'],
            'steps': [
                'query analysis', 'broad vector retrieval', 'aggressive ranking',
                'deduplication', 'graph-guided retrieval', 'compact evidence synthesis',
                'strict citation validation', 'stop'
            ][:self.max_steps]
        }

    def _query_terms(self, q):
        stop = {
            'compare', 'financial', 'health', 'companies', 'company', 'annual',
            'report', 'analysis', 'sector', 'risks', 'outlook', 'performance',
            'between', 'with', 'from', 'what', 'which', 'their', 'and', 'the',
            'this', 'that', 'over', 'under', 'into', 'how', 'does', 'show'
        }
        terms = re.findall(r'[A-Za-z][A-Za-z0-9&.-]{2,}', q.lower())
        phrases = re.findall(
            r'\b[A-Z][A-Za-z&.-]{2,}(?:\s+[A-Z][A-Za-z&.-]{2,}){0,3}\b', q
        )
        return list(dict.fromkeys([x.lower() for x in phrases] + [x for x in terms if x not in stop]))[:28]

    def _graph_context(self, q):
        anchors = []
        for term in self._query_terms(q):
            anchors.extend(self.graph.find_entities(term, limit=3))
        ids = list(dict.fromkeys(x['id'] for x in anchors))
        # Graph is used for navigation only; do not send graph relations to synthesis.
        hops = self.graph.multi_hop(ids, hops=1, limit=20)
        return anchors, hops

    @staticmethod
    def _tokens(text):
        return set(re.findall(r'[a-z0-9]+', str(text).lower()))

    @classmethod
    def _rank_docs(cls, query, docs, metas, distances):
        """Aggressive hybrid ranking: semantic + lexical + phrase + primary-source quality."""
        q_tokens = cls._tokens(query)
        q_terms = [t for t in re.findall(r'[a-z0-9]+', query.lower()) if len(t) >= 3]
        ranked = []
        for i, (text, meta) in enumerate(zip(docs, metas)):
            meta = meta or {}
            text_s = str(text)
            tokens = cls._tokens(text_s)
            overlap = len(q_tokens & tokens) / max(1, len(q_tokens))
            term_hits = sum(1 for t in q_terms if t in text_s.lower())
            lexical = min(1.0, term_hits / max(1, min(len(q_terms), 10)))
            distance = float(distances[i]) if i < len(distances) and distances[i] is not None else 1.0
            semantic = max(0.0, min(1.0, 1.0 - distance))
            stype = str(meta.get('source_type', '')).lower()
            title = str(meta.get('title', '')).lower()
            primary = 0.10 if ('annual' in stype or 'annual report' in title) else 0.0
            page_bonus = 0.02 if meta.get('page') not in (None, '') else 0.0
            score = 0.50 * semantic + 0.25 * overlap + 0.23 * lexical + primary + page_bonus
            ranked.append((score, i))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        return ranked

    @classmethod
    def _content_key(cls, text):
        normalized = re.sub(r'\s+', ' ', str(text).lower()).strip()
        return hashlib.sha1(normalized.encode('utf-8')).hexdigest()

    @classmethod
    def _is_near_duplicate(cls, text, accepted_tokens):
        tokens = cls._tokens(text)
        if len(tokens) < 8:
            return False
        for old in accepted_tokens:
            inter = len(tokens & old)
            union = len(tokens | old)
            if union and inter / union >= 0.78:
                return True
        return False

    @classmethod
    def _relevant_excerpt(cls, text, query, max_chars=None):
        """Select a compact passage around the densest query-term evidence."""
        max_chars = max_chars or cls.EXCERPT_CHARS
        text = re.sub(r'\s+', ' ', str(text)).strip()
        if len(text) <= max_chars:
            return text
        terms = [t for t in cls._tokens(query) if len(t) >= 3]
        sentences = re.split(r'(?<=[.!?])\s+', text)
        scored = []
        for idx, sent in enumerate(sentences):
            low = sent.lower()
            hits = sum(low.count(t) for t in terms)
            if hits:
                scored.append((hits, -idx, idx, sent))
        if not scored:
            return text[:max_chars].rstrip() + '…'
        scored.sort(reverse=True)
        center = scored[0][2]
        selected = [sentences[center]]
        total = len(selected[0])
        left, right = center - 1, center + 1
        while left >= 0 or right < len(sentences):
            candidates = []
            if left >= 0:
                candidates.append((sum(sentences[left].lower().count(t) for t in terms), left))
            if right < len(sentences):
                candidates.append((sum(sentences[right].lower().count(t) for t in terms), right))
            if not candidates:
                break
            _, idx = max(candidates)
            candidate = sentences[idx]
            if total + len(candidate) + 1 > max_chars:
                break
            if idx == left:
                selected.insert(0, candidate)
                left -= 1
            else:
                selected.append(candidate)
                right += 1
            total += len(candidate) + 1
        return ' '.join(selected).strip()

    def run(self, q):
        evidence = []
        seen_hashes = set()
        accepted_tokens = []
        stagnant = 0
        anchors, hops = self._graph_context(q)

        self.trace.append({
            'step': 1, 'action': 'query analysis + graph anchoring', 'query': q,
            'source_type': 'local graph', 'source_count': len(anchors),
            'new_entities': len(anchors), 'new_claims': 0,
            'evidence_score': 0, 'decision': 'CONTINUE'
        })

        # Broad retrieval with several query formulations; only the final top 8–10 go to Ollama.
        queries = [q, f'{q} revenue growth margin cash flow', f'{q} drivers risks outlook']
        if hops:
            names = [str(x.get('name', '')) for x in hops[:5] if x.get('name')]
            if names:
                queries.append(q + ' ' + ' '.join(names))

        for step, nq in enumerate(queries[:max(3, min(self.max_steps, 4))], start=2):
            try:
                r = self.vector.search(nq, k=20)
                docs = r.get('documents', [[]])[0] if r else []
                metas = r.get('metadatas', [[]])[0] if r else []
                distances = r.get('distances', [[]])[0] if r else []
            except Exception as exc:
                docs, metas, distances = [], [], []
                self.trace.append({'step': step, 'action': 'vector retrieval error', 'query': nq,
                                   'source_type': 'ChromaDB', 'source_count': 0,
                                   'new_entities': 0, 'new_claims': 0, 'evidence_score': 0,
                                   'decision': 'CONTINUE', 'error': str(exc)})
                continue

            ranked = self._rank_docs(nq, docs, metas, distances)
            added = 0
            for rank, (score, idx) in enumerate(ranked, 1):
                if len(evidence) >= 30:
                    break
                text = docs[idx]
                meta = metas[idx] or {}
                key = meta.get('evidence_id') or meta.get('chunk_id') or self._content_key(text)
                if key in seen_hashes or self._is_near_duplicate(text, accepted_tokens):
                    continue
                seen_hashes.add(key)
                accepted_tokens.append(self._tokens(text))
                evidence.append({
                    'text': text, **meta, 'retrieval_score': round(score, 4),
                    'retrieval_rank': rank, 'retrieval_query': nq
                })
                added += 1

            stagnant = stagnant + 1 if added == 0 else 0
            self.trace.append({
                'step': step, 'action': 'broad retrieval + aggressive ranking + deduplication',
                'query': nq, 'source_type': 'ChromaDB', 'source_count': added,
                'new_entities': len(hops) if step == 2 else 0, 'new_claims': 0,
                'evidence_score': round(min(1.0, len(evidence) / 20), 3),
                'decision': 'STOP' if len(evidence) >= 20 or stagnant >= 2 else 'CONTINUE'
            })
            if len(evidence) >= 20 or stagnant >= 2:
                break

        # Final diversity pass: prefer distinct sources/years while preserving rank.
        evidence.sort(key=lambda x: -float(x.get('retrieval_score', 0)))
        selected = []
        source_counts = {}
        for item in evidence:
            src = str(item.get('source') or item.get('title') or 'Unknown').lower()
            count = source_counts.get(src, 0)
            if count >= 2:
                continue
            selected.append(item)
            source_counts[src] = count + 1
            if len(selected) >= self.MAX_EVIDENCE:
                break
        # Annual reports are the primary source. If they do not contain enough
        # support for the requested financial data, use the supplied structured
        # financials dataset as a secondary evidence source. We never calculate
        # or invent missing values here.
        financial_evidence = []
        try:
            loader = LocalFinancialData()
            financial_evidence = loader.search(q, str(FINANCIALS_DIR), top_k=self.MAX_FINANCIAL_EVIDENCE)
        except Exception as exc:
            self.trace.append({
                'step': len(self.trace) + 1, 'action': 'financials dataset lookup error',
                'query': q, 'source_type': 'financials_dataset', 'source_count': 0,
                'new_entities': 0, 'new_claims': 0, 'evidence_score': 0,
                'decision': 'CONTINUE', 'error': str(exc)
            })

        # Only append structured financials when annual-report evidence is thin.
        # The annual-report evidence remains first in the evidence packet.
        if financial_evidence and len(selected) < self.MAX_EVIDENCE:
            needed = self.MAX_EVIDENCE - len(selected)
            selected.extend(financial_evidence[:min(self.MAX_FINANCIAL_EVIDENCE, needed)])
        elif financial_evidence:
            # Even with enough annual-report passages, add only a small secondary
            # corroboration set when the query explicitly asks for a metric/data point.
            metric_terms = ('sales', 'revenue', 'growth', 'margin', 'profit', 'cash flow',
                            'free cash flow', 'ebit', 'ebitda', 'fcf', 'roce', 'roe')
            if any(t in q.lower() for t in metric_terms):
                selected.extend(financial_evidence[:1])
                selected = selected[:self.MAX_EVIDENCE]

        return self._synthesize(q, selected)

    def _synthesize(self, q, evidence):
        # Compact, relevant excerpts are the only source material supplied to the LLM.
        compact = []
        for i, e in enumerate(evidence, 1):
            src = e.get('source') or e.get('title') or 'Unknown source'
            page = e.get('page')
            loc = f' page={page}' if page not in (None, '') else ''
            excerpt = self._relevant_excerpt(e.get('text', ''), q)
            tag = 'F' + str(i) if str(e.get('source_type', '')).lower() == 'financials_dataset' else 'E' + str(i)
            compact.append(f'[{tag}] source={src}{loc}\n{excerpt}')

        ctx = '\n\n'.join(compact)
        prompt = f"""Financial question: {q}

Use ONLY the evidence passages below.

Rules:
- Every factual claim must cite one or more [E#] or [F#] passages inline.
- Never invent, estimate, interpolate, or import outside facts, figures, dates, or sources.
- [E#] = annual-report evidence and has priority. [F#] = the supplied financials dataset and may be used when the annual reports do not establish the requested data.
- Never present an [F#] value as if it came from an annual report.
- If a requested fact is not supported, write exactly: "Not established by the retrieved evidence."
- Label interpretation as "Inference" and cite the supporting [E#].
- If evidence conflicts, state the conflict and cite both sides.
- Do not treat graph relationships, model knowledge, or assumptions as evidence.
- Prefer higher-ranked evidence and corroboration.
- Keep the report concise and decision-useful.

Output exactly these sections:
## Executive Summary
## Key Financial Findings
## Drivers / Competitive Position
## Risks and Outlook
## Evidence Gaps / Conflicts
## Sources

EVIDENCE:
{ctx}"""

        try:
            return self.llm.chat(
                prompt,
                system=(
                    'You are a conservative financial research analyst. Evidence outranks fluency. '
                    'A claim without an [E#] or [F#] citation is prohibited. Do not use outside knowledge. Annual-report evidence has priority; the supplied financials dataset is the permitted secondary source for data absent from the reports.'
                ),
                temperature=0
            )
        except Exception as e:
            # Optional controlled OpenAI fallback. It uses the same evidence-only prompt.
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                try:
                    from llm.openai_client import OpenAIClient
                    return OpenAIClient().chat(prompt, system=(
                        'You are a conservative financial research analyst. Evidence outranks fluency. '
                        'A claim without an [E#] or [F#] citation is prohibited. Do not use outside knowledge. Annual-report evidence has priority; the supplied financials dataset is the permitted secondary source for data absent from the reports.'
                    ), temperature=0)
                except Exception as openai_exc:
                    e = RuntimeError(f'Ollama failed: {e}; OpenAI fallback failed: {type(openai_exc).__name__}: {openai_exc}')
            # Safe fallback: expose evidence, not a generated narrative.
            lines = [
                '# Financial Research Report', '', '## Generation status',
                f'Local synthesis unavailable: {e}', '',
                'No unsupported financial conclusions were generated.', '',
                '## Retrieved Evidence'
            ]
            for i, x in enumerate(evidence, 1):
                src = x.get('source') or x.get('title') or 'Unknown source'
                page = x.get('page')
                loc = f' p.{page}' if page not in (None, '') else ''
                tag = 'F' + str(i) if str(x.get('source_type', '')).lower() == 'financials_dataset' else 'E' + str(i)
                lines.append(f'### [{tag}] {src}{loc}')
                lines.append(self._relevant_excerpt(x.get('text', ''), q))
                lines.append('')
            return '\n'.join(lines)
