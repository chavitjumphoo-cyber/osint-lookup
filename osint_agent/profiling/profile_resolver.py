"""รวม artifact เป็นโปรไฟล์และ entity ที่ตรวจสอบย้อนกลับได้"""

from __future__ import annotations

import re
from collections import defaultdict
from hashlib import sha1

from . import entity_extractor
from .collectors import username_from_url
from .normalizers import fold_key

CONFIDENCE_ORDER = {"Confirmed": 4, "Probable": 3, "Unverified": 2, "Inferred": 1, "Speculative": 0}
NAME_STOP = {
    "log in", "sign up", "facebook", "instagram", "see all", "photos", "more",
    "about", "home", "contact", "login", "github", "gitlab", "pinterest", "twitch",
    "join facebook", "see instagram", "posts", "reels",
}


def _entity_id(kind: str, value: str) -> str:
    return "ent_" + sha1(f"{kind}|{fold_key(value)}".encode()).hexdigest()[:14]


def extract_entities(artifacts: list[dict]) -> list[dict]:
    entities = []
    seen = set()
    for artifact in artifacts:
        if artifact.get("source_type") == "search_result":
            text = f"{artifact.get('title', '')}\n{artifact.get('content', '')}"
        else:
            text = artifact.get("content", "")
        found = entity_extractor.extract(text)
        for kind in ("names", "emails", "phones", "handles", "urls", "locations", "organizations", "interests", "dates"):
            key = "name" if kind == "names" else kind.rstrip("s")
            for value in found.get(kind, []):
                signature = (key, fold_key(value), artifact["artifact_id"])
                if signature in seen:
                    continue
                seen.add(signature)
                entities.append(
                    {
                        "entity_id": _entity_id(key, value),
                        "type": key,
                        "value": value,
                        "source_artifact": artifact["artifact_id"],
                        "source_url": artifact.get("source_url", ""),
                        "confidence": "Probable" if key in {"email", "phone"} else "Unverified",
                    }
                )
    return entities


def resolve_profiles(artifacts: list[dict], entities: list[dict]) -> list[dict]:
    profiles: dict[str, dict] = {}
    by_artifact = defaultdict(list)
    for entity in entities:
        by_artifact[entity["source_artifact"]].append(entity)

    for artifact in artifacts:
        if artifact.get("source_type") != "profile":
            continue
        platform = artifact.get("platform") or "unknown"
        username = artifact.get("author") or username_from_url(artifact.get("source_url", "")) or ""
        key = f"{platform}:{fold_key(username)}" if username else f"{platform}:{artifact['artifact_id']}"
        profile = profiles.setdefault(
            key,
            {
                "key": key,
                "platform": platform,
                "username": username,
                "url": artifact.get("source_url", ""),
                "display_names": [],
                "bios": [],
                "locations": [],
                "organizations": [],
                "interests": [],
                "emails": [],
                "phones": [],
                "handles": [],
                "links": [],
                "education": [],
                "languages": [],
                "explicit_links": [],
                "name_observations": [],
                "relations": [],
                "family_names": [],
                "dates": [],
                "evidence": [],
                "confidence": "Unverified",
            },
        )
        profile["evidence"].append(artifact["artifact_id"])
        title = re.sub(r"\s+", " ", (artifact.get("title") or "")).strip()
        if title and fold_key(title) not in NAME_STOP and 2 < len(title) < 80:
            if not any(title in existing or existing in title for existing in profile["display_names"]):
                profile["display_names"].append(title)
        metadata = artifact.get("metadata") or {}
        avatar = metadata.get("avatar")
        if avatar and not profile.get("avatar"):
            profile["avatar"] = avatar
            from hashlib import sha1

            profile["avatar_hash"] = sha1(avatar.encode()).hexdigest()[:16]
        for field in ("emails", "phones", "organizations", "education", "languages"):
            for entry in (metadata.get("profile_fields") or {}).get(field, []):
                value = entry.get("value") if isinstance(entry, dict) else entry
                if value and value not in profile[field]:
                    profile[field].append(value)
        for entry in (metadata.get("profile_fields") or {}).get("websites", []):
            value = entry.get("value") if isinstance(entry, dict) else entry
            if value and value not in profile["links"]:
                profile["links"].append(value)
        for observation in (metadata.get("profile_fields") or {}).get("name_observations", []):
            if observation not in profile["name_observations"]:
                profile["name_observations"].append(observation)
            family = observation.get("family_name") if isinstance(observation, dict) else None
            if family and family not in profile["family_names"]:
                profile["family_names"].append(family)
        for relation in (metadata.get("profile_fields") or {}).get("relations", []):
            if relation not in profile["relations"]:
                profile["relations"].append(relation)
        content = artifact.get("content", "")
        if content and len(content) > 15:
            if not any(content[:80] in existing for existing in profile["bios"]):
                profile["bios"].append(content[:400])

        for entity in by_artifact.get(artifact["artifact_id"], []):
            target = {
                "name": "display_names",
                "email": "emails",
                "phone": "phones",
                "handle": "handles",
                "url": "links",
                "location": "locations",
                "organization": "organizations",
                "interest": "interests",
                "date": "dates",
            }.get(entity["type"])
            if not target:
                continue
            value = re.sub(r"\s+", " ", entity["value"]).strip()
            if target == "display_names":
                if fold_key(value) in NAME_STOP or len(value) < 3 or len(value) > 80:
                    continue
                if any(value in existing or existing in value for existing in profile[target]):
                    continue
            if value and value not in profile[target]:
                profile[target].append(value)

        if CONFIDENCE_ORDER.get(artifact.get("confidence", ""), 0) > CONFIDENCE_ORDER.get(profile["confidence"], 0):
            profile["confidence"] = artifact["confidence"]

    for profile in profiles.values():
        if len(profile["evidence"]) >= 2:
            profile["confidence"] = "Probable"
        if profile["display_names"] and " " in profile["display_names"][0]:
            profile["confidence"] = "Confirmed" if len(profile["evidence"]) >= 2 else "Probable"
    return sorted(profiles.values(), key=lambda item: len(item["evidence"]), reverse=True)


def profile_entities(profile: dict) -> dict:
    return {
        "entity_id": _entity_id("profile", profile["key"]),
        "platform": profile["platform"],
        "usernames": {profile["platform"]: profile["username"]} if profile["username"] else {},
        "emails": profile["emails"],
        "phones": profile["phones"],
        "display_names": profile["display_names"],
        "evidence": profile["evidence"],
    }
