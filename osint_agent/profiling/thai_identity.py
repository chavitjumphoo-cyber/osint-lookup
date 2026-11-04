"""แยกชื่อไทย/อังกฤษเป็น given/family name และสกัดคำบอกความสัมพันธ์"""

from __future__ import annotations

import re

TITLES = (
    "นาย", "นางสาว", "นาง", "ดร.", "ด.ช.", "ด.ญ.", "พล.ต.อ.", "พล.ต.ท.", "พ.ต.อ.", "ร.ต.อ.",
    "mr.", "mrs.", "ms.", "dr.",
)
THAI_RE = re.compile(r"^[ก-๙]+$")
EN_RE = re.compile(r"^[A-Za-z][A-Za-z'\-]+$")
TOKEN_RE = re.compile(r"[ก-๙]+|[A-Za-z][A-Za-z'\-]+")

RELATION_TERMS = {
    "บิดา": ["บิดา", "พ่อ", "คุณพ่อ", "father", "dad"],
    "มารดา": ["มารดา", "แม่", "คุณแม่", "mother", "mom"],
    "พี่น้อง": ["พี่ชาย", "พี่สาว", "น้องชาย", "น้องสาว", "พี่น้อง", "sibling", "brother", "sister"],
    "คู่สมรส": ["ภรรยา", "สามี", "เมีย", "wife", "husband", " spouse", "คู่สมรส"],
    "บุตร": ["ลูกชาย", "ลูกสาว", "บุตร", "ธิดา", "son", "daughter", "child"],
    "ญาติ": ["ญาติ", "น้า", "อา", "ลุง", "ป้า", "cousin", "relative", "หลาน"],
    "เพื่อน": ["เพื่อน", "friend"],
    "เพื่อนร่วมงาน": ["เพื่อนร่วมงาน", "หัวหน้า", "ลูกน้อง", "colleague", "boss", "employee"],
    "คู่ค้า": ["คู่ค้า", "หุ้นส่วน", "partner", "business partner", "กรรมการ"],
}

RELATION_PATTERNS = [
    re.compile(
        r"(?P<term>" + "|".join(t for terms in RELATION_TERMS.values() for t in terms) + r")"
        r"[^.\n]{0,20}?(?P<name>[ก-๙]{2,20}(?:\s+[ก-๙]{2,20}){0,2}|[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,2})",
        re.I,
    ),
    re.compile(
        r"(?P<name>[ก-๙]{2,20}(?:\s+[ก-๙]{2,20}){0,2}|[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,2})"
        r"[^.\n]{0,12}?(?:เป็น|คือ)\s*(?P<term>" + "|".join(t for terms in RELATION_TERMS.values() for t in terms) + r")",
        re.I,
    ),
]


def _term_to_type(term: str) -> str:
    lowered = term.lower()
    for kind, terms in RELATION_TERMS.items():
        if any(lowered == word.lower() or lowered in word.lower() for word in terms):
            return kind
    return "unknown"


def parse_name(text: str) -> dict | None:
    """คืน full_name/given/family พร้อม script — คืน None ถ้าไม่ใช่ชื่อที่พอเชื่อได้"""
    raw = re.sub(r"\s+", " ", (text or "")).strip(" ,.-|·")
    if not raw or len(raw) > 80:
        return None
    for title in TITLES:
        if raw.lower().startswith(title.lower()):
            raw = raw[len(title):].strip()
            break
    tokens = TOKEN_RE.findall(raw)
    if len(tokens) < 2 or len(tokens) > 3:
        return None
    if not all(THAI_RE.match(t) or EN_RE.match(t) for t in tokens):
        return None
    script = "thai" if any(THAI_RE.match(t) for t in tokens) else "english"
    return {
        "full_name": " ".join(tokens),
        "given_name": tokens[0],
        "family_name": tokens[-1],
        "name_script": script,
    }


def extract_relations(text: str) -> list[dict]:
    text = re.sub(r"\s+", " ", text or "")
    found = []
    for pattern in RELATION_PATTERNS:
        for match in pattern.finditer(text):
            term = match.group("term")
            name = consume_title(match.group("name"))
            if not name:
                continue
            snippet = text[max(0, match.start() - 40) : match.end() + 40].strip()
            found.append(
                {
                    "name": name,
                    "relationship": _term_to_type(term),
                    "term": term,
                    "snippet": snippet,
                }
            )
    return found


def consume_title(name: str) -> str:
    value = name.strip()
    for title in TITLES:
        if value.lower().startswith(title.lower()):
            value = value[len(title):].strip()
    return value


def surname_queries(surname: str, context_terms: list[str] | None = None) -> list[str]:
    queries = [f'"{surname}"']
    for phrase in ("ครอบครัว", "พี่น้อง", "บิดา", "มารดา", "ญาติ"):
        queries.append(f'"{surname}" {phrase}')
    for term in (context_terms or [])[:2]:
        if term:
            queries.append(f'"{surname}" "{term}"')
    return list(dict.fromkeys(queries))
