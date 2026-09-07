from sectors.it import SECTOR_CONFIG as IT
from sectors.pharma import SECTOR_CONFIG as PHARMA

SECTORS = {'IT': IT, 'Pharma': PHARMA}


def _company_terms(cfg):
    """Return company/entity terms without assuming a specific config schema."""
    values = []
    for key in ('companies', 'primary_entities'):
        raw = cfg.get(key, []) if isinstance(cfg, dict) else []
        if isinstance(raw, str):
            raw = [raw]
        values.extend(str(x).strip() for x in raw if str(x).strip())
    return values


def route(query):
    q = (query or '').lower()
    scores = {}
    for name, cfg in SECTORS.items():
        terms = [name.lower()] + [c.lower() for c in _company_terms(cfg)]
        # Avoid duplicate terms and count each matching term once.
        scores[name] = sum(1 for t in set(terms) if t and t in q)

    ranked = sorted(scores, key=scores.get, reverse=True)
    return [x for x in ranked if scores[x] > 0] or list(SECTORS.keys())
