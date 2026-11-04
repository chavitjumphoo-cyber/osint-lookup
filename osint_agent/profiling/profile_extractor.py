"""สกัดฟิลด์โปรไฟล์แบบมีหลักฐานจาก artifact ที่เปิดอ่านแล้ว"""

from __future__ import annotations

import json
import re

from . import entity_extractor, thai_identity
from .normalizers import fold_key

FIELDS = (
    "display_names", "aliases", "usernames", "bio", "locations", "organizations",
    "education", "websites", "emails", "phones", "avatar_urls", "account_created_at",
    "followers", "following", "repositories", "posts", "languages", "interests",
    "published_dates", "relations", "name_observations",
)

ORG_RE = re.compile(r"(?:works? at|working at|employed at|@)\s+([A-Z][\w&.\- ]{2,40})")
EDU_RE = re.compile(r"(?:studied at|education|มหาวิทยาลัย|คณะ)\s*([\wก-๙&.\- ]{2,50})")
CREATED_RE = re.compile(r"(?:joined|created_at|member since|สมัครเมื่อ)\s*([A-Za-z0-9 ,\-/]{4,30})")
FOLLOW_RE = re.compile(r"([\d,\.]+)\s*(?:followers|ผู้ติดตาม)", re.I)
LANG_RE = re.compile(r"\b(python|javascript|typescript|rust|go|java|php|ruby|kotlin|swift|sql)\b", re.I)


def empty_fields() -> dict:
    return {field: [] for field in FIELDS}


def _add(fields: dict, key: str, value: str, artifact: dict, confidence: str = "Unverified") -> None:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if not value or len(value) > 200:
        return
    entry = {
        "value": value,
        "source_artifact": artifact["artifact_id"],
        "source_url": artifact.get("source_url", ""),
        "snippet": artifact.get("content", "")[:200],
        "confidence": confidence,
    }
    if all(fold_key(item["value"]) != fold_key(value) for item in fields[key]):
        fields[key].append(entry)


def extract(artifact: dict) -> dict:
    fields = empty_fields()
    content = artifact.get("content", "")
    title = artifact.get("title", "")
    meta = artifact.get("metadata") or {}

    if title:
        _add(fields, "display_names", title, artifact, "Probable")
        parsed = thai_identity.parse_name(title)
        if parsed:
            fields["name_observations"].append(
                {
                    **parsed,
                    "source_artifact": artifact["artifact_id"],
                    "source_url": artifact.get("source_url", ""),
                    "snippet": content[:200],
                    "confidence": "Probable",
                }
            )
    if artifact.get("author"):
        _add(fields, "usernames", artifact["author"], artifact, "Probable")
    if meta.get("bio"):
        _add(fields, "bio", meta["bio"], artifact, "Probable")
    if meta.get("avatar"):
        _add(fields, "avatar_urls", meta["avatar"], artifact, "Probable")

    found = entity_extractor.extract(content)
    mapping = {
        "names": ("display_names", "Unverified"),
        "emails": ("emails", "Probable"),
        "phones": ("phones", "Probable"),
        "handles": ("usernames", "Unverified"),
        "urls": ("websites", "Unverified"),
        "locations": ("locations", "Unverified"),
        "organizations": ("organizations", "Unverified"),
        "interests": ("interests", "Unverified"),
        "dates": ("published_dates", "Unverified"),
    }
    for key, (target, confidence) in mapping.items():
        for value in found.get(key, []):
            if key == "urls" and artifact.get("source_url", "") in value:
                continue
            _add(fields, target, value, artifact, confidence)

    for match in ORG_RE.finditer(content):
        _add(fields, "organizations", match.group(1).strip(" .,-"), artifact, "Unverified")
    for match in EDU_RE.finditer(content):
        _add(fields, "education", match.group(1).strip(" .,-"), artifact, "Unverified")
    for match in CREATED_RE.finditer(content):
        _add(fields, "account_created_at", match.group(1), artifact, "Unverified")
    follow = FOLLOW_RE.search(content)
    if follow:
        _add(fields, "followers", follow.group(1), artifact, "Unverified")
    for match in LANG_RE.finditer(content):
        _add(fields, "languages", match.group(1).lower(), artifact, "Unverified")

    for relation in thai_identity.extract_relations(content):
        fields["relations"].append(
            {
                "name": relation["name"],
                "relationship": relation["relationship"],
                "term": relation["term"],
                "snippet": relation["snippet"],
                "source_artifact": artifact["artifact_id"],
                "source_url": artifact.get("source_url", ""),
                "confidence": "Unverified",
            }
        )

    return {"artifact_id": artifact["artifact_id"], **fields}


def extract_with_llm(artifact: dict, client=None) -> dict:
    try:
        from vendor._compat import complete_text

        raw = complete_text(
            "สกัดโปรไฟล์จากข้อความหน้าเว็บ ตอบ JSON เท่านั้นตาม schema: "
            + json.dumps({field: [] for field in FIELDS})
            + " ห้ามแต่งข้อมูลที่ไม่มีในข้อความ ใส่เฉพาะค่าที่เห็นจริง",
            [{"role": "user", "content": artifact.get("content", "")[:6000]}],
            max_tokens=1500,
            client=client,
        )
        match = re.search(r"\{.*\}", raw, re.S)
        payload = json.loads(match.group(0)) if match else {}
    except Exception:  # noqa: BLE001
        return extract(artifact)

    fields = extract(artifact)
    for key in FIELDS:
        for value in payload.get(key) or []:
            if isinstance(value, str):
                _add(fields, key, value, artifact, "Probable")
    return fields


def to_profile_fields(extractions: list[dict]) -> dict:
    merged = empty_fields()
    for extraction in extractions:
        for key in FIELDS:
            merged[key].extend(extraction.get(key, []))
    return merged
