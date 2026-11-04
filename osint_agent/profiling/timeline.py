"""สร้าง timeline จากวันที่ที่พบใน artifact"""

from __future__ import annotations

import re

ISO_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")


def build(artifacts: list[dict], entities: list[dict]) -> list[dict]:
    dates_by_artifact: dict[str, list[str]] = {}
    for entity in entities:
        if entity["type"] == "date":
            dates_by_artifact.setdefault(entity["source_artifact"], []).append(entity["value"])

    events = []
    for artifact in artifacts:
        dates = dates_by_artifact.get(artifact["artifact_id"], [])
        if artifact.get("published_at"):
            dates.append(artifact["published_at"])
        for date in dates:
            events.append(
                {
                    "date": date,
                    "title": artifact.get("title") or artifact.get("source_url", ""),
                    "platform": artifact.get("platform", ""),
                    "artifact_id": artifact["artifact_id"],
                    "source_url": artifact.get("source_url", ""),
                }
            )
    return sorted(events, key=lambda item: item["date"])
