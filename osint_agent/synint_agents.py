"""SYNINT-inspired Advanced Agents
- PersonProfileAgent: รวบรวมข้อมูลบุคคลจากหลายแหล่ง
- UsernameCorrelationAgent: สร้าง username variants และหาความเชื่อมโยง
- EmailHarvestAgent: สร้างรูปแบบอีเมลที่เป็นไปได้
- IdentityCandidateAgent: วิเคราะห์ identity candidates
- DarkWebMonitorAgent: ค้นหาข้อมูลรั่วไหล (scaffold)
"""

import re
from collections import Counter
from typing import Any


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PersonProfileAgent — รวบรวมข้อมูลบุคคล
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def person_profile_agent(collected_evidence: dict[str, Any]) -> dict[str, Any]:
    """รวบรวมข้อมูลบุคคลจาก evidence ที่เก็บมาทั้งหมด

    Args:
        collected_evidence: dict ที่มี keys อย่าง:
            - "names": list[str]
            - "emails": list[str]
            - "phones": list[str]
            - "usernames": list[str]
            - "organizations": list[str]
            - "locations": list[str]
            - "social_profiles": list[dict]

    Returns:
        dict with profile summary, direct/inferred evidence
    """
    aliases = collected_evidence.get("names", [])
    usernames = collected_evidence.get("usernames", [])
    emails = collected_evidence.get("emails", [])
    phones = collected_evidence.get("phones", [])
    organizations = collected_evidence.get("organizations", [])
    locations = collected_evidence.get("locations", [])
    social_profiles = collected_evidence.get("social_profiles", [])

    # แยก direct evidence (มีแหล่งที่มาชัด) กับ inferred (อนุมาน)
    direct_evidence = []
    inferred_evidence = []

    if social_profiles:
        direct_evidence.append(f"พบโปรไฟล์โซเชียล {len(social_profiles)} แห่ง")
    if emails:
        direct_evidence.append(f"พบอีเมล {len(emails)} อันจากหลักฐาน")
    if phones:
        direct_evidence.append(f"พบเบอร์โทร {len(phones)} หมายเลขจากหลักฐาน")

    if aliases and not social_profiles:
        inferred_evidence.append(f"อนุมานชื่อ {len(aliases)} รูปแบบจากข้อความที่เก็บมา")
    if usernames and len(usernames) > 1:
        inferred_evidence.append(f"อนุมาน username variants {len(usernames)} รูปแบบ")

    profile_summary = {
        "alias_count": len(set(aliases)),
        "username_count": len(set(usernames)),
        "email_count": len(set(emails)),
        "phone_count": len(set(phones)),
        "organization_count": len(set(organizations)),
        "location_count": len(set(locations)),
        "social_profile_count": len(social_profiles),
        "direct_evidence_count": len(direct_evidence),
        "inferred_evidence_count": len(inferred_evidence),
    }

    # คำนวณ confidence score
    evidence_count = len(direct_evidence)
    confidence = min(0.3 + evidence_count * 0.1, 0.9)

    return {
        "profile_summary": profile_summary,
        "aliases": sorted(set(aliases)),
        "usernames": sorted(set(usernames)),
        "emails": sorted(set(emails)),
        "phones": sorted(set(phones)),
        "organizations": sorted(set(organizations)),
        "locations": sorted(set(locations)),
        "direct_evidence": direct_evidence,
        "inferred_evidence": inferred_evidence,
        "confidence_score": round(confidence, 2),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UsernameCorrelationAgent — สร้าง username variants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def generate_username_variants(seed: str) -> list[str]:
    """สร้าง username variants จาก seed username

    จาก: john.doe
    ได้: johndoe, john_doe, jdoe, doej, j.doe, doe.john
    """
    base = re.sub(r"[^A-Za-z0-9._-]", "", seed.strip().lower())
    if not base:
        return []

    parts = re.split(r"[._-]+", base)
    variants = {
        base,
        base.replace(".", ""),
        base.replace("_", ""),
        base.replace("-", ""),
    }

    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        variants.update({
            f"{first}.{last}",
            f"{first}_{last}",
            f"{first}{last}",
            f"{first[0]}{last}" if first else last,
            f"{last}{first[0]}" if first else last,
            f"{last}.{first}",
        })

    return sorted(variants)


def username_correlation_agent(target: str, collected_text: str) -> dict[str, Any]:
    """วิเคราะห์ username correlation — หา variants ที่ปรากฏใน corpus

    Args:
        target: username seed (เช่น "john.doe", "@johndoe", "https://twitter.com/johndoe")
        collected_text: ข้อความทั้งหมดที่เก็บมา

    Returns:
        dict with generated_variants, matched_variants, clusters
    """
    # ดึง seed จาก target
    seed = target.strip()
    if seed.startswith("@"):
        seed = seed[1:]
    elif "@" in seed and "://" not in seed:
        # email format → ใช้ local part
        seed = seed.split("@", 1)[0]
    elif "://" in seed:
        # URL → ใช้ส่วนท้าย
        seed = seed.rstrip("/").split("/")[-1].lstrip("@")
    # else: ใช้ seed ตามที่เป็นอยู่

    variants = generate_username_variants(seed)
    if not variants:
        return {
            "seed": seed,
            "generated_variants": [],
            "matched_variants": [],
            "clusters": [],
            "confidence_notes": ["ไม่สามารถสร้าง variants ได้"],
        }

    # หา variants ที่ปรากฏใน corpus
    corpus_lower = collected_text.lower()
    matched = [v for v in variants if v.lower() in corpus_lower]

    clusters = []
    if matched:
        clusters.append({
            "cluster_id": "reuse_cluster_1",
            "variants": matched,
            "evidence": "พบใน corpus ที่เก็บมา",
        })

    confidence = min(0.3 + len(matched) * 0.1, 0.8) if matched else 0.1

    return {
        "seed": seed,
        "generated_variants": variants,
        "matched_variants": matched,
        "clusters": clusters,
        "confidence_score": round(confidence, 2),
        "confidence_notes": [
            "ผลลัพธ์มาจาก local corpus เท่านั้น",
            "ไม่ได้ยืนยันว่ามีบัญชีจริงบนแพลตฟอร์ม",
        ],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EmailHarvestAgent — สร้างรูปแบบอีเมลที่เป็นไปได้
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE_ACCOUNTS = [
    "admin", "info", "support", "sales", "billing", "contact",
    "security", "helpdesk", "press", "legal", "privacy", "abuse",
]

PERSON_PATTERNS = [
    "{first}.{last}",
    "{first}{last}",
    "{f}{last}",
    "{first}",
    "{last}.{first}",
    "{first}_{last}",
]

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")


def email_harvest_agent(domain: str, first_name: str = "john", last_name: str = "doe") -> dict[str, Any]:
    """สร้างรูปแบบอีเมลที่เป็นไปได้ (hypothesis-only)

    Args:
        domain: โดเมน (เช่น "example.com")
        first_name: ชื่อตัวอย่าง
        last_name: นามสกุลตัวอย่าง

    Returns:
        dict with generated_addresses
    """
    candidates = []

    # Role accounts
    for local in ROLE_ACCOUNTS:
        candidates.append(f"{local}@{domain}")

    # Person patterns
    for pattern in PERSON_PATTERNS:
        local = pattern.format(first=first_name, last=last_name, f=first_name[0])
        candidates.append(f"{local}@{domain}")

    generated = [addr for addr in dict.fromkeys(candidates) if EMAIL_RE.match(addr)]

    return {
        "domain": domain,
        "generated_addresses": generated,
        "generated_count": len(generated),
        "email_hypothesis_only": True,
        "confidence_note": "เป็นการสร้างรูปแบบที่เป็นไปได้เท่านั้น ไม่ได้ยืนยันว่ามีอีเมลจริง",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IdentityCandidateAgent — วิเคราะห์ identity candidates
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def identity_candidate_agent(entities: list[dict[str, Any]]) -> dict[str, Any]:
    """วิเคราะห์ identity candidates — หาว่า entities หลายตัวเป็นคนเดียวกันหรือไม่

    Args:
        entities: list of dicts with keys like:
            - "name": str
            - "email": str
            - "phone": str
            - "username": str
            - "source": str

    Returns:
        dict with identity_candidates
    """
    if len(entities) < 2:
        return {
            "identity_candidates": [],
            "candidate_count": 0,
            "reason": "ต้องมีอย่างน้อย 2 entities",
        }

    candidates = []

    # หา entities ที่มี email ตรงกัน
    email_groups: dict[str, list[dict]] = {}
    for entity in entities:
        email = entity.get("email")
        if email:
            email_groups.setdefault(email, []).append(entity)

    for email, group in email_groups.items():
        if len(group) > 1:
            candidates.append({
                "match_type": "email_match",
                "signal": email,
                "entities": [e.get("name") or e.get("username") for e in group],
                "confidence": "high",
                "source_count": len(group),
            })

    # หา entities ที่มี username ตรงกัน
    username_groups: dict[str, list[dict]] = {}
    for entity in entities:
        username = entity.get("username")
        if username:
            username_groups.setdefault(username, []).append(entity)

    for username, group in username_groups.items():
        if len(group) > 1:
            candidates.append({
                "match_type": "username_match",
                "signal": username,
                "entities": [e.get("name") or e.get("email") for e in group],
                "confidence": "medium",
                "source_count": len(group),
            })

    return {
        "identity_candidates": candidates,
        "candidate_count": len(candidates),
        "confirmation_policy": "ต้องมีผู้ตรวจสอบยืนยัน — ห้าม auto-merge",
        "llm_confirmation": False,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DarkWebMonitorAgent — scaffold สำหรับค้นข้อมูลรั่วไหล
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def shannon_entropy(text: str) -> float:
    """คำนวณ Shannon entropy — วัดความซับซ้อนของข้อความ"""
    if not text:
        return 0.0
    import math
    counts = Counter(text)
    total = len(text)
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            probability = count / total
            entropy -= probability * math.log2(probability)
    return entropy


def darkweb_monitor_agent(target: str) -> dict[str, Any]:
    """Dark web monitoring scaffold — เตรียม hooks สำหรับค้น breach data

    Args:
        target: email, username, หรือ domain ที่ต้องการค้น

    Returns:
        dict with search_target, entropy, supported_sources
    """
    entropy = shannon_entropy(target)

    return {
        "search_target": target,
        "target_entropy": round(entropy, 4),
        "agent_classification": "enrichment_scaffold",
        "local_sources_supported": [
            "breach corpus",
            "paste dumps",
            "onion index snapshots",
            "forum scrape archives",
        ],
        "matching_hooks": {
            "exact_match": True,
            "fuzzy_match": True,
            "domain_match": True,
            "email_match": True,
            "username_match": True,
        },
        "note": "scaffold เท่านั้น — ต้อง integrate กับ breach database จริง",
    }
