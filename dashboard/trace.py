import pandas as pd

def trace_dataframe(trace):
    return pd.DataFrame(trace or [], columns=[
        "step","action","query","source_type","source_count",
        "new_entities","new_claims","evidence_score","decision"
    ])

def summary(trace):
    df = trace_dataframe(trace)
    if df.empty:
        return {"steps": 0, "sources": 0, "evidence_score": 0}
    return {
        "steps": int(len(df)),
        "sources": int(df["source_count"].fillna(0).sum()),
        "evidence_score": float(df["evidence_score"].fillna(0).iloc[-1])
    }
