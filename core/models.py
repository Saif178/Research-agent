from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List
import hashlib

@dataclass
class Source:
    source_id: str
    title: str
    url: str = ""
    publisher: str = ""
    source_type: str = "web"
    retrieved_at: str = ""
    published_at: str = ""
    accession: str = ""
    page: int | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Chunk:
    chunk_id: str
    text: str
    source_id: str
    document_id: str
    page: int | None = None
    entity_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Entity:
    entity_id: str
    name: str
    entity_type: str
    aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Relation:
    relation_id: str
    subject_id: str
    predicate: str
    object_id: str
    source_id: str
    confidence: float = 0.0
    evidence_chunk_id: str = ""

@dataclass
class Evidence:
    chunk: Chunk
    source: Source
    score: float = 0.0
    hop: int = 0
    verification: Dict[str, Any] = field(default_factory=dict)

def stable_id(*parts: str) -> str:
    return hashlib.sha256("||".join(parts).encode()).hexdigest()[:24]

def to_dict(obj):
    return asdict(obj)
