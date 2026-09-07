import math, re
from typing import Optional

_NUM = r"(?:\(?-?\d[\d,]*(?:\.\d+)?\)?|[-+]?\d+(?:\.\d+)?)"

def _num(s: str) -> Optional[float]:
    if s is None: return None
    s=s.strip().replace(',', '')
    neg=s.startswith('(') and s.endswith(')')
    s=s.strip('()')
    try:
        v=float(s)
        return -v if neg else v
    except Exception: return None

def _find(text, labels):
    for label in labels:
        p=rf"{re.escape(label)}[^\n\r]{{0,100}}?({_NUM})"
        m=re.search(p,text,re.I)
        if m:
            return _num(m.group(1)), m.group(0)
    return None, None

def calculate_from_evidence(query: str, evidence_text: str):
    q=query.lower()
    out=[]
    # These calculations only run when both inputs are explicitly present in retrieved website evidence.
    if any(x in q for x in ['revenue growth','sales growth','yoy growth','year-over-year growth']):
        cur,_c=_find(evidence_text,['current revenue','revenue','sales'])
        prev,_p=_find(evidence_text,['previous revenue','prior revenue','revenue previous year','sales previous year'])
        if cur is not None and prev not in (None,0): out.append((cur-prev)/abs(prev)*100)
    if any(x in q for x in ['gross margin','gross profit margin']):
        gp,_=_find(evidence_text,['gross profit'])
        rev,_=_find(evidence_text,['revenue','sales'])
        if gp is not None and rev not in (None,0): out.append(gp/rev*100)
    if any(x in q for x in ['operating margin','ebit margin','operating profit margin']):
        op,_=_find(evidence_text,['operating profit','operating income','ebit'])
        rev,_=_find(evidence_text,['revenue','sales'])
        if op is not None and rev not in (None,0): out.append(op/rev*100)
    if any(x in q for x in ['free cash flow margin','fcf margin','free cash flow / sales']):
        fcf,_=_find(evidence_text,['free cash flow'])
        rev,_=_find(evidence_text,['revenue','sales'])
        if fcf is not None and rev not in (None,0): out.append(fcf/rev*100)
    if any(x in q for x in ['debt to equity','debt/equity']):
        debt,_=_find(evidence_text,['total debt','debt'])
        eq,_=_find(evidence_text,['total equity','shareholders equity','stockholders equity'])
        if debt is not None and eq not in (None,0): out.append(debt/eq)
    if any(x in q for x in ['cagr','compound annual growth']):
        vals=re.findall(rf"(?:start|beginning|initial)[^\n\r]{{0,80}}?({_NUM}).*?(?:end|ending|final)[^\n\r]{{0,80}}?({_NUM})", evidence_text, re.I|re.S)
        if vals:
            a,b=_num(vals[0][0]),_num(vals[0][1])
            yrs=re.search(r'(\d+)\s*(?:years?|yrs?)',q)
            n=int(yrs.group(1)) if yrs else None
            if a and b and a>0 and b>0 and n and n>0: out.append(((b/a)**(1/n)-1)*100)
    return out
