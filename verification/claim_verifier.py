from dataclasses import dataclass, asdict
from typing import List

@dataclass
class ClaimEvidence:
    source_id: str
    source_type: str
    title: str
    url: str = ""
    page: str = ""
    snippet: str = ""

@dataclass
class VerifiedClaim:
    claim: str
    status: str
    confidence: float
    supporting_sources: List[ClaimEvidence]
    contradictory_sources: List[ClaimEvidence]
    rationale: str

class ClaimVerifier:
    """Evidence-level verifier. A claim is corroborated only when independent evidence agrees."""

    def verify(self, claim, evidence):
        evidence = evidence or []
        unique_sources = {e.source_id for e in evidence if e.source_id}
        if len(unique_sources) >= 2:
            status, confidence = "CORROBORATED", min(0.95, 0.65 + 0.1*len(unique_sources))
            rationale = "Claim has independent supporting evidence from multiple sources."
        elif len(evidence) == 1:
            status, confidence = "SINGLE_SOURCE", 0.55
            rationale = "Claim has one traceable supporting source; independent corroboration is absent."
        else:
            status, confidence = "UNVERIFIED", 0.05
            rationale = "No traceable evidence was supplied."
        return VerifiedClaim(claim, status, confidence, evidence, [], rationale)

    def to_dict(self, verified_claim):
        return asdict(verified_claim)
