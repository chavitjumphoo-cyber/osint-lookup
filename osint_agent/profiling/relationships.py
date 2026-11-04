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


def explicit_relations(profiles: list[dict]) -> list[dict]:
    """ความสัมพันธ์ที่แหล่งระบุตรง ๆ พร้อมหลักฐาน"""
    found = []
    seen = set()
    for profile in profiles:
        for relation in profile.get("relations", []):
            key = (relation.get("name", "").lower(), relation.get("relationship"))
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "name": relation.get("name"),
                    "relationship": relation.get("relationship"),
                    "term": relation.get("term"),
                    "snippet": relation.get("snippet"),
                    "source_url": relation.get("source_url"),
                    "artifact_id": relation.get("source_artifact"),
                    "confidence": relation.get("confidence", "Unverified"),
                    "via_profile": profile["key"],
                }
            )
    return found
