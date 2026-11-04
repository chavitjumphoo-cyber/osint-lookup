"""ให้คะแนนความเป็นเจ้าของบัญชีเดียวกันจาก metadata ที่มีหลักฐาน"""

from __future__ import annotations

from difflib import SequenceMatcher

from .normalizers import fold_key

WEIGHTS = {
    "same_email": 1.0,
    "same_phone": 1.0,
    "explicit_link": 0.95,
    "source_native_id": 0.95,
    "same_avatar_hash": 0.8,
    "same_full_name": 0.55,
    "bio_similarity": 0.45,
    "same_org_or_location": 0.35,
    "same_username": 0.15,
    "interest_overlap": 0.1,
}

VERDICTS = ("Confirmed", "Probable", "Possible", "Contradicted", "Unverified")


def _values(profile: dict, key: str) -> set[str]:
    return {fold_key(str(v)) for v in profile.get(key, []) if str(v).strip()}


def _ratio(a: set[str], b: set[str]) -> float:
    best = 0.0
    for left in a:
        for right in b:
            best = max(best, SequenceMatcher(None, left, right).ratio())
    return best


def score_pair(a: dict, b: dict) -> dict:
    score = 0.0
    signals = []
    conflicts = []

    if _values(a, "emails") & _values(b, "emails"):
        score += WEIGHTS["same_email"]
        signals.append("same_email")
    if _values(a, "phones") & _values(b, "phones"):
        score += WEIGHTS["same_phone"]
        signals.append("same_phone")
    if a.get("explicit_links") and fold_key(b.get("key", "")) in {fold_key(str(x)) for x in a["explicit_links"]}:
        score += WEIGHTS["explicit_link"]
        signals.append("explicit_link")
    if a.get("avatar_hash") and a.get("avatar_hash") == b.get("avatar_hash"):
        score += WEIGHTS["same_avatar_hash"]
        signals.append("same_avatar_hash")

    name_ratio = _ratio(_values(a, "display_names"), _values(b, "display_names"))
    if name_ratio >= 0.95:
        score += WEIGHTS["same_full_name"]
        signals.append("same_full_name")
    elif name_ratio >= 0.6:
        score += WEIGHTS["same_full_name"] * 0.5
        signals.append("partial_name")

    bio_a = " ".join(_values(a, "bios"))
    bio_b = " ".join(_values(b, "bios"))
    bio_ratio = _ratio({bio_a}, {bio_b}) if bio_a and bio_b else 0.0
    if bio_ratio >= 0.7:
        score += WEIGHTS["bio_similarity"]
        signals.append("bio_similarity")

    if (_values(a, "organizations") & _values(b, "organizations")) or (
        _values(a, "locations") & _values(b, "locations")
    ):
        score += WEIGHTS["same_org_or_location"]
        signals.append("same_org_or_location")

    if a.get("username") and fold_key(a.get("username", "")) == fold_key(b.get("username", "")):
        score += WEIGHTS["same_username"]
        signals.append("same_username")

    if _values(a, "interests") & _values(b, "interests"):
        score += WEIGHTS["interest_overlap"]
        signals.append("interest_overlap")

    a_surname = _values(a, "display_names")
    b_surname = _values(b, "display_names")
    if name_ratio < 0.4 and a_surname and b_surname and "same_email" not in signals:
        conflicts.append("different_display_name")

    normalized = min(1.0, round(score, 2))
    hard = {"same_email", "same_phone"} & set(signals)
    if conflicts and normalized < 0.6:
        verdict = "Contradicted"
    elif hard:
        verdict = "Confirmed"
    elif normalized >= 0.9:
        verdict = "Probable"
    elif normalized >= 0.3:
        verdict = "Possible"
    else:
        verdict = "Unverified"
    return {"score": normalized, "verdict": verdict, "signals": signals, "conflicts": conflicts}
