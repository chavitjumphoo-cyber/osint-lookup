"""สร้าง view model สำหรับหน้า Analysis — identifier → profile → 6D"""

from __future__ import annotations

from . import cognitive, narrative, profile_resolver, relationships
from . import timeline as timeline_mod
from .identity_score import score_pair
from .normalizers import fold_key

PIVOT_TOOLS = {
    "email": ["breach_check", "gravatar_lookup", "web_search"],
    "phone": ["scan_phone_advanced", "web_search"],
    "username": ["scan_profiles", "web_search"],
    "url": ["fetch_page"],
    "name": ["web_search"],
    "organization": ["web_search"],
    "family_name": ["search_surname", "search_family_relation"],
}


def _confidence(occurrences: int, tiers: set[str]) -> str:
    if occurrences >= 3 and ("direct" in tiers or "Probable" in tiers):
        return "Probable"
    if occurrences >= 2:
        return "Unverified"
    return "Unverified"


def build(store, run_id: str) -> dict:
    run = store.get_run(run_id)
    if not run:
        raise KeyError(run_id)
    artifacts = store.list_artifacts(run_id)
    entities = profile_resolver.extract_entities(artifacts)
    profiles = profile_resolver.resolve_profiles(artifacts, entities)
    events = timeline_mod.build(artifacts, entities)
    rels = relationships.co_occurring_entities(artifacts, entities)

    grouped: dict[tuple[str, str], dict] = {}
    for entity in entities:
        if entity["type"] not in {"email", "phone", "username", "url", "name", "organization", "location", "handle"}:
            continue
        kind = "username" if entity["type"] == "handle" else entity["type"]
        key = (kind, fold_key(entity["value"]))
        item = grouped.setdefault(
            key,
            {
                "value": entity["value"],
                "type": kind,
                "source_artifacts": [],
                "source_urls": [],
                "profiles": [],
                "confidence": "Unverified",
            },
        )
        if entity["source_artifact"] not in item["source_artifacts"]:
            item["source_artifacts"].append(entity["source_artifact"])
        if entity.get("source_url") and entity["source_url"] not in item["source_urls"]:
            item["source_urls"].append(entity["source_url"])

    for profile in profiles:
        for kind, bucket, field in (
            ("email", profile["emails"], "emails"),
            ("phone", profile["phones"], "phones"),
            ("username", profile["handles"], "usernames"),
            ("url", profile["links"], "websites"),
            ("name", profile["display_names"], "display_names"),
            ("organization", profile["organizations"], "organizations"),
        ):
            for value in profile.get(field, []) if field in profile else bucket:
                key = (kind, fold_key(str(value)))
                if key in grouped and profile["key"] not in grouped[key]["profiles"]:
                    grouped[key]["profiles"].append(profile["key"])

    identifiers = []
    for (kind, _), item in grouped.items():
        item["occurrences"] = len(item["source_artifacts"])
        item["confidence"] = _confidence(item["occurrences"], set())
        item["next_pivots"] = PIVOT_TOOLS.get(kind, [])
        identifiers.append(item)
    identifiers.sort(key=lambda item: (-item["occurrences"], item["type"], item["value"]))

    pairs = []
    for index, left in enumerate(profiles):
        for right in profiles[index + 1 :]:
            scored = score_pair(left, right)
            pairs.append(
                {
                    "left": left["key"],
                    "right": right["key"],
                    "left_url": left["url"],
                    "right_url": right["url"],
                    "verdict": scored["verdict"],
                    "score": scored["score"],
                    "signals": scored["signals"],
                }
            )
    pairs.sort(key=lambda item: -item["score"])

    cog = cognitive.evaluate(profiles, artifacts, entities)
    confirmed = [p for p in profiles if p["confidence"] in {"Confirmed", "Probable"}]

    data_for_narrative = {
        "identity": {
            "names": sorted({n for p in profiles for n in p["display_names"]}),
            "family_names": sorted({f for p in profiles for f in p.get("family_names", [])}),
            "emails": sorted({e for p in profiles for e in p["emails"]}),
            "phones": sorted({ph for p in profiles for ph in p["phones"]}),
            "locations": sorted({loc for p in profiles for loc in p["locations"]}),
            "organizations": sorted({o for p in profiles for o in p["organizations"]}),
        },
        "profiles_detail": profiles,
        "interests": sorted({i for p in profiles for i in p["interests"]}),
        "cognitive": cog,
        "explicit_relations": [r for p in profiles for r in p.get("relations", [])],
        "contradictions": [],
        "limitations": [],
    }

    return {
        "run": run,
        "narrative": narrative.build(data_for_narrative, artifacts),
        "identifiers": identifiers,
        "profiles": profiles,
        "ownership": pairs,
        "cognitive": cog,
        "relationships": rels,
        "timeline": events,
        "candidates": store.list_candidates(run_id),
        "names": [
            {"full_name": o.get("full_name"), "given_name": o.get("given_name"),
             "family_name": o.get("family_name"), "confidence": o.get("confidence"),
             "source_url": o.get("source_url"), "artifact_id": o.get("source_artifact")}
            for p in profiles for o in p.get("name_observations", [])
        ],
        "family_names": sorted({f for p in profiles for f in p.get("family_names", [])}),
        "explicit_relations": [
            r for p in profiles for r in p.get("relations", [])
        ],
        "counts": {
            "identifiers": len(identifiers),
            "profiles": len(profiles),
            "confirmed_profiles": len(confirmed),
            "contradictions": len([p for p in pairs if p["verdict"] == "Contradicted"]),
        },
        "who": {
            "likely_names": sorted({n for p in confirmed for n in p["display_names"]}),
            "platforms": sorted({p["platform"] for p in confirmed}),
            "organizations": sorted({o for p in confirmed for o in p["organizations"]}),
            "locations": sorted({loc for p in confirmed for loc in p["locations"]}),
            "confidence": "Probable" if confirmed else "Unverified",
        },
    }
