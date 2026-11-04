"""Artifact — หลักฐานหนึ่งชิ้นที่อ้างกลับได้ (หน้าเว็บ, ผลค้น, โปรไฟล์, โพสต์)"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha1

CONFIDENCE = {"Confirmed", "Probable", "Unverified", "Inferred", "Speculative"}
SOURCE_TYPES = {"search_result", "profile", "post", "document", "api", "page"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Artifact:
    source_url: str
    source_type: str
    source_tool: str
    content: str = ""
    platform: str = ""
    title: str = ""
    author: str = ""
    published_at: str = ""
    entities: list[dict] = field(default_factory=list)
    status: str = "ok"
    output_hash: str = ""
    confidence: str = "Unverified"
    query: str = ""
    metadata: dict = field(default_factory=dict)
    retrieved_at: str = ""
    artifact_id: str = ""

    def __post_init__(self) -> None:
        if self.source_type not in SOURCE_TYPES:
            self.source_type = "page"
        if self.confidence not in CONFIDENCE:
            self.confidence = "Unverified"
        if not self.retrieved_at:
            self.retrieved_at = _now()
        if not self.artifact_id:
            raw = f"{self.source_url}|{self.source_type}|{self.content[:500]}"
            self.artifact_id = "art_" + sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "source_tool": self.source_tool,
            "platform": self.platform,
            "title": self.title,
            "author": self.author,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "content": self.content[:20000],
            "entities": self.entities,
            "status": self.status,
            "output_hash": self.output_hash,
            "confidence": self.confidence,
            "query": self.query,
            "metadata": self.metadata,
        }
