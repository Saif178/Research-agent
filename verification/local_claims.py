from dataclasses import dataclass,asdict
@dataclass
class Claim:
    text:str; status:str; confidence:float; evidence:list; rationale:str
class LocalClaimVerifier:
    def verify(self,claim,evidence):
        src={}
        for e in evidence:
            sid=e.get('source_id') or e.get('document_id') or e.get('source')
            if sid: src.setdefault(sid,[]).append(e)
        n=len(src)
        if n>=2: status,conf,rat='CORROBORATED',min(.95,.65+.10*n),'Independent local sources corroborate the claim.'
        elif n==1: status,conf,rat='SINGLE_SOURCE',.55,'The claim is traceable to one local source.'
        else: status,conf,rat='UNVERIFIED',.05,'No supporting local evidence was found.'
        return Claim(claim,status,conf,evidence,rat)
    def as_dict(self,c): return asdict(c)
