"""Corpus — คลังกลางของ artifacts ต่อ run พร้อม dedupe และสรุป"""

from __future__ import annotations

from collections import Counter

from ..services.store import RunStore
from .artifacts import Artifact


class Corpus:
    def __init__(self, store: RunStore, run_id: str):
        self.store = store
        self.run_id = run_id
        self._seen: set[str] = set()
        for item in store.list_artifacts(run_id):
            self._seen.add(item["artifact_id"])

    def add(self, artifact: Artifact) -> bool:
        if artifact.artifact_id in self._seen:
            return False
        self._seen.add(artifact.artifact_id)
        self.store.add_artifact(self.run_id, artifact.to_dict())
        return True

    def artifacts(self, source_type: str | None = None) -> list[dict]:
        return self.store.list_artifacts(self.run_id, source_type)

    def profiles(self) -> list[dict]:
        return self.artifacts("profile")

    def search_results(self) -> list[dict]:
        return self.artifacts("search_result")

    def urls(self) -> set[str]:
        return {item["source_url"] for item in self.artifacts() if item.get("source_url")}

    def summary(self) -> dict:
        artifacts = self.artifacts()
        return {
            "total": len(artifacts),
            "by_type": dict(Counter(item["source_type"] for item in artifacts)),
            "by_platform": dict(Counter(item.get("platform") or "unknown" for item in artifacts)),
        }
