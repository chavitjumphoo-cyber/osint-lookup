"""วิเคราะห์ความสัมพันธ์และบุคคลแวดล้อมจาก corpus"""

from __future__ import annotations

from collections import Counter


def co_occurring_entities(artifacts: list[dict], entities: list[dict]) -> list[dict]:
    by_artifact: dict[str, list[dict]] = {}
    for entity in entities:
        by_artifact.setdefault(entity["source_artifact"], []).append(entity)

    pairs: Counter[tuple[str, str]] = Counter()
    for items in by_artifact.values():
        names = [item["value"] for item in items if item["type"] == "name"]
        handles = [item["value"] for item in items if item["type"] == "handle"]
        for name in names:
            for handle in handles:
                pairs[(name, handle)] += 1

    return [
        {"name": name, "handle": handle, "strength": count}
        for (name, handle), count in pairs.most_common(20)
    ]


def repeated_platforms(artifacts: list[dict]) -> list[dict]:
    counts: Counter[str] = Counter()
    urls: dict[str, list[str]] = {}
    for artifact in artifacts:
        platform = artifact.get("platform")
        if artifact.get("source_type") == "profile" and platform:
            counts[platform] += 1
            urls.setdefault(platform, []).append(artifact.get("source_url", ""))
    return [
        {"platform": platform, "count": count, "urls": urls[platform][:5]}
        for platform, count in counts.most_common()
    ]
