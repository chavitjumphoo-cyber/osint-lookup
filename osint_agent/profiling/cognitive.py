"""6D Cognitive Profiling จากหลักฐาน — deterministic ก่อน, LLM เสริมได้

ทุกมิติคืน assessment/confidence/rationale/evidence และพูดว่า "ประเมินไม่ได้" เมื่อหลักฐานไม่พอ
"""

from __future__ import annotations

import re
from collections import Counter

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
FIRST_PERSON = ("ผม", "ฉัน", "เรา", "i ", "my ", "me ")
QUESTION_RE = re.compile(r"[?？]")
EXCLAIM_RE = re.compile(r"[!！]")

POLITICS = ["เลือกตั้ง", "การเมือง", "รัฐบาล", "พรรค", "politics", "election"]
RELIGION = ["พระ", "วัด", "ศาสนา", "ธรรมะ", "religion", "buddhist"]
ENVIRONMENT = ["สิ่งแวดล้อม", "โลกร้อน", "climate", "recycle"]
TECH_TERMS = ["python", "javascript", "rust", "docker", "kubernetes", "linux", "github", "api", "devops"]
CRYPTO_TERMS = ["bitcoin", "ethereum", "crypto", "blockchain", "คริปโต"]

DIMENSIONS = (
    "identity",
    "geo_temporal",
    "psychological",
    "technical",
    "ideological",
    "opsec",
)


def _texts(artifacts: list[dict]) -> list[str]:
    return [a.get("content", "").strip() for a in artifacts if len(a.get("content", "").strip()) >= 80]


def _evidence(artifacts: list[dict], predicate) -> list[str]:
    return [a["artifact_id"] for a in artifacts if predicate(a)]


def _result(assessment: str, confidence: str, rationale: str, evidence: list[str], metrics=None) -> dict:
    return {
        "assessment": assessment,
        "confidence": confidence,
        "rationale": rationale,
        "evidence": sorted(set(evidence))[:30],
        "metrics": metrics or {},
    }


def evaluate(profiles: list[dict], artifacts: list[dict], entities: list[dict]) -> dict:
    by_type: dict[str, list[dict]] = {}
    for entity in entities:
        by_type.setdefault(entity["type"], []).append(entity)

    platforms = {p["platform"] for p in profiles}
    names = {name for p in profiles for name in p["display_names"]}
    locations = {e["value"] for e in by_type.get("location", [])}
    emails = {e["value"] for e in by_type.get("email", [])}
    phones = {e["value"] for e in by_type.get("phone", [])}
    orgs = {value for p in profiles for value in p.get("organizations", [])}
    education = {value for p in profiles for value in p.get("education", [])}
    languages = {value for p in profiles for value in p.get("languages", [])}
    websites = {value for p in profiles for value in p.get("links", [])}
    texts = _texts(artifacts)

    results: dict[str, dict] = {}

    if profiles:
        results["identity"] = _result(
            f"พบโปรไฟล์ {len(profiles)} แห่งบน {len(platforms)} แพลตฟอร์ม; ชื่อต่างกัน {len(names)}; องค์กร {len(orgs)}; การศึกษา {len(education)}",
            "Probable" if len(platforms) >= 3 else "Unverified",
            "วัดจากจำนวนแพลตฟอร์มและชื่อที่สอดคล้องกัน; username ซ้ำเพียงอย่างเดียวไม่ยืนยัน",
            [eid for p in profiles for eid in p["evidence"]],
            {"platforms": len(platforms), "profiles": len(profiles), "distinct_names": len(names), "orgs": len(orgs)},
        )
    else:
        results["identity"] = _result("ประเมินไม่ได้ — ยังไม่พบโปรไฟล์", "Unverified", "ไม่มีหลักฐานโปรไฟล์", [])

    geo_evidence = [e["source_artifact"] for e in by_type.get("location", [])]
    if locations:
        results["geo_temporal"] = _result(
            f"พบสถานที่สาธารณะ {len(locations)} แห่ง: {', '.join(sorted(locations)[:5])}",
            "Probable" if len(geo_evidence) >= 2 else "Unverified",
            "เป็นสถานที่ที่ระบุในโปรไฟล์/โพสต์ ไม่ใช่ที่อยู่ปัจจุบัน",
            geo_evidence,
            {"locations": len(locations)},
        )
    else:
        results["geo_temporal"] = _result(
            "ประเมินไม่ได้ — ไม่พบสถานที่หรือสัญญาณเวลา", "Unverified", "ไม่มีข้อมูล geo/เวลา", []
        )

    if len(texts) >= 3:
        joined = "\n".join(texts)
        lengths = [len(t) for t in texts]
        metrics = {
            "samples": len(texts),
            "avg_chars": round(sum(lengths) / len(lengths)),
            "emoji": len(EMOJI_RE.findall(joined)),
            "questions": len(QUESTION_RE.findall(joined)),
            "exclamations": len(EXCLAIM_RE.findall(joined)),
            "first_person": sum(joined.lower().count(token) for token in FIRST_PERSON),
        }
        traits = []
        if metrics["emoji"] >= 5:
            traits.append("แสดงอารมณ์ผ่านอีโมจิค่อนข้างมาก")
        if metrics["first_person"] >= 3:
            traits.append("อ้างถึงตัวเองบ่อย")
        if metrics["questions"] >= 3:
            traits.append("ตั้งคำถาม/ชวนสนทนา")
        if metrics["avg_chars"] > 300:
            traits.append("เขียนข้อความยาว")
        results["psychological"] = _result(
            "สมมติฐาน OCEAN เบื้องต้น: " + ("; ".join(traits) if traits else "ยังไม่เห็นรูปแบบชัด"),
            "Speculative",
            "วิเคราะห์จากสถิติข้อความ ไม่ใช่แบบทดสอบจิตวิทยา",
            _evidence(artifacts, lambda a: len(a.get("content", "")) >= 80),
            metrics,
        )
    else:
        results["psychological"] = _result(
            f"ประเมินไม่ได้ — ข้อความยาวไม่พอ ({len(texts)}/3 ชิ้น)", "Unverified", "ต้องมีข้อความอย่างน้อย 3 ชิ้น", []
        )

    tech_hits = Counter(language for language in languages)
    if orgs:
        pass
    short_texts = [a.get("content", "") for a in artifacts if a.get("content")]
    for text in short_texts:
        low = text.lower()
        tech_hits.update(term for term in TECH_TERMS if term in low)
        tech_hits.update(term for term in CRYPTO_TERMS if term in low)
    if tech_hits:
        results["technical"] = _result(
            "พบสัญญาณเทคนิค: " + ", ".join(term for term, _ in tech_hits.most_common(6)),
            "Probable" if sum(tech_hits.values()) >= 3 else "Unverified",
            "นับคำศัพท์เทคนิคที่ปรากฏในเนื้อหาที่เปิดอ่าน",
            _evidence(artifacts, lambda a: any(t in a.get("content", "").lower() for t in TECH_TERMS + CRYPTO_TERMS)),
            {"hits": sum(tech_hits.values())},
        )
    else:
        results["technical"] = _result("ประเมินไม่ได้ — ไม่พบสัญญาณเทคนิค", "Unverified", "ไม่พบคำศัพท์เทคนิค", [])

    ideo = {}
    for label, words in (("การเมือง", POLITICS), ("ศาสนา", RELIGION), ("สิ่งแวดล้อม", ENVIRONMENT)):
        hits = sum(1 for text in texts if any(word in text.lower() for word in words))
        if hits >= 2:
            ideo[label] = hits
    if ideo:
        results["ideological"] = _result(
            "พบการกล่าวถึงซ้ำ: " + ", ".join(f"{k} ({v} ครั้ง)" for k, v in ideo.items()),
            "Unverified",
            "นับการปรากฏซ้ำในหลายข้อความ ไม่ได้แปลว่าเป็นจุดยืนหลัก",
            _evidence(artifacts, lambda a: any(w in a.get("content", "").lower() for w in POLITICS + RELIGION + ENVIRONMENT)),
            ideo,
        )
    else:
        results["ideological"] = _result(
            "ประเมินไม่ได้ — ไม่พบประเด็นอุดมการณ์ที่กล่าวซ้ำ", "Unverified", "ต้องพบอย่างน้อย 2 ข้อความ", []
        )

    exposures = []
    if emails:
        exposures.append(f"อีเมล {len(emails)} รายการ")
    if phones:
        exposures.append(f"เบอร์ {len(phones)} รายการ")
    if locations:
        exposures.append(f"สถานที่ {len(locations)} แห่ง")
    if names:
        exposures.append(f"ชื่อจริง/ชื่อที่แสดง {len(names)} แบบ")
    if websites:
        exposures.append(f"เว็บไซต์ {len(websites)} แห่ง")
    if exposures:
        results["opsec"] = _result(
            "ข้อมูลที่เปิดเผย: " + ", ".join(exposures),
            "Probable",
            "รายงานเฉพาะสิ่งที่พบในที่สาธารณะ",
            [e["source_artifact"] for kind in ("email", "phone", "location") for e in by_type.get(kind, [])],
            {"emails": len(emails), "phones": len(phones), "locations": len(locations), "websites": len(websites)},
        )
    else:
        results["opsec"] = _result("ประเมินไม่ได้ — ไม่พบข้อมูลที่เปิดเผย", "Unverified", "ไม่พบ identifier", [])

    return results
