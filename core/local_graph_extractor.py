import re
from core.models import stable_id

# Fast, deterministic extraction used for every chunk. No network calls.
METRIC_PATTERNS = [
    ("Revenue", r"\b(?:revenue|sales|net sales|turnover)\b"),
    ("Gross Profit", r"\b(?:gross profit|gross margin)\b"),
    ("Operating Profit", r"\b(?:operating profit|operating income|EBIT)\b"),
    ("EBITDA", r"\bEBITDA\b"),
    ("Net Income", r"\b(?:net income|profit after tax|PAT|net profit)\b"),
    ("Free Cash Flow", r"\b(?:free cash flow|FCF)\b"),
    ("Capex", r"\b(?:capital expenditure|capital expenditures|CapEx|capex)\b"),
    ("R&D", r"\b(?:research and development|R&D)\b"),
]


def _clean_name(x):
    return re.sub(r"\s+", " ", x.strip(" ,.;:()[]{}\"'"))


def extract_fast(text, company, chunk_id):
    """Extract high-confidence graph anchors without an LLM.

    This intentionally favors precision and repeatability over guessing. Every
    entity is tied to the evidence chunk through a MENTIONED_IN edge.
    """
    entities = []
    relations = []
    seen = {}

    def add(name, typ, **meta):
        name = _clean_name(name)
        if not name or len(name) < 2:
            return None
        key = (typ.lower(), name.lower())
        if key in seen:
            return seen[key]
        eid = stable_id(typ, name.lower())
        seen[key] = eid
        entities.append({"id": eid, "name": name, "type": typ, "metadata": meta})
        return eid

    company_id = add(company, "Company")
    for metric, pat in METRIC_PATTERNS:
        if re.search(pat, text, re.I):
            mid = add(metric, "Metric")
            relations.append((company_id, "HAS_METRIC", mid, 0.95))

    # Common competitor phrasing in annual reports.
    competitor_patterns = [
        r"(?:compet(?:e|es|ing) with|competitors? (?:include|are)|against)\s+([^.;\n]{2,100})",
        r"(?:market share .*? versus|versus|vs\.)\s+([A-Z][A-Za-z0-9& .-]{2,60})",
    ]
    for pat in competitor_patterns:
        for m in re.finditer(pat, text, re.I):
            raw = m.group(1)
            for part in re.split(r",| and |;", raw):
                name = _clean_name(part)
                if 2 <= len(name) <= 60 and not re.search(r"\b(the|our|its|these|those)\b$", name, re.I):
                    oid = add(name, "Competitor")
                    relations.append((company_id, "COMPETES_WITH", oid, 0.75))

    # Technologies/products are only extracted when introduced by strong cues.
    cue_patterns = [
        ("Technology", r"(?:technology|platform|solution|system)\s+(?:called|named)?\s*([A-Z][A-Za-z0-9][A-Za-z0-9 ._-]{2,45})"),
        ("Product", r"(?:product|brand|drug|medicine)\s+(?:called|named)?\s*([A-Z][A-Za-z0-9][A-Za-z0-9 ._-]{2,45})"),
    ]
    for typ, pat in cue_patterns:
        for m in re.finditer(pat, text):
            name = _clean_name(m.group(1))
            oid = add(name, typ)
            relations.append((company_id, "HAS_" + typ.upper(), oid, 0.65))

    # Geography names from explicit business wording, deliberately conservative.
    for m in re.finditer(r"(?:operations|presence|sales|revenue|business)\s+(?:in|across)\s+([A-Z][A-Za-z .&-]{2,50})", text):
        name = _clean_name(m.group(1))
        gid = add(name, "Geography")
        relations.append((company_id, "OPERATES_IN", gid, 0.70))

    return entities, relations
