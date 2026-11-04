"""สร้างสมมติฐานคำค้นและ pivot ตามชนิด target"""

from __future__ import annotations

import re

from .normalizers import fold_key

SCAM_TERMS = ["มิจฉาชีพ", "โกง", "scam", "บัญชีม้า", "ฉ้อโกง"]
PLATFORM_SITES = ["facebook.com", "pantip.com", "twitter.com", "x.com", "instagram.com", "tiktok.com"]


def phone_variants(number: str) -> list[str]:
    digits = re.sub(r"\D", "", number)
    if digits.startswith("66"):
        local = "0" + digits[2:]
        e164 = "+" + digits
    elif digits.startswith("0"):
        local = digits
        e164 = "+66" + digits[1:]
    else:
        return [number]
    spaced = f"{local[:3]} {local[3:6]} {local[6:]}"
    dashed = f"{local[:3]}-{local[3:6]}-{local[6:]}"
    return list(dict.fromkeys([e164, digits, local, spaced, dashed]))


def username_variants(username: str) -> list[str]:
    base = username.strip().lstrip("@")
    variants = [base, base.casefold(), base.replace(".", ""), base.replace("_", ""), base.replace("-", "")]
    seen = set()
    stable = []
    for variant in variants:
        key = fold_key(variant)
        if variant and key not in seen:
            seen.add(key)
            stable.append(variant)
    return stable


def search_queries(target: str, target_type: str, known_names: list[str] | None = None) -> list[str]:
    names = [name for name in (known_names or []) if name]
    queries: list[str] = []

    if target_type == "phone":
        for variant in phone_variants(target)[:5]:
            queries.append(f'"{variant}"')
            for term in SCAM_TERMS[:2]:
                queries.append(f'"{variant}" {term}')
            for site in PLATFORM_SITES[:2]:
                queries.append(f'"{variant}" site:{site}')

    elif target_type == "username":
        for variant in username_variants(target)[:2]:
            queries.append(f'"{variant}"')
            for site in PLATFORM_SITES[:3]:
                queries.append(f'"{variant}" site:{site}')
        for name in names[:2]:
            queries.append(f'"{name}" "{target.lstrip("@")}"')

    elif target_type == "email":
        queries.append(f'"{target}"')
        queries.append(f'"{target}" (github OR linkedin OR resume)')
        local = target.split("@", 1)[0]
        if local:
            queries.append(f'"{local}"')

    elif target_type in {"domain", "url"}:
        host = re.sub(r"^https?://", "", target).split("/")[0]
        queries.append(f'"{host}"')
        for term in ("phishing", "มิจฉาชีพ", "scam", "review"):
            queries.append(f'"{host}" {term}')

    elif target_type == "name":
        from .thai_identity import parse_name, surname_queries

        parsed = parse_name(target)
        queries.append(f'"{target}"')
        for site in PLATFORM_SITES[:3]:
            queries.append(f'"{target}" site:{site}')
        if parsed:
            queries.append(f'"{parsed["given_name"]}" "{parsed["family_name"]}"')
            queries.extend(surname_queries(parsed["family_name"])[:5])

    else:
        queries.append(f'"{target}"')
        if " " in target:
            parts = target.split()
            queries.append(f'"{parts[0]}" "{parts[-1]}"')
            queries.append(f'"{target}" (facebook OR linkedin OR github)')
        for name in names[:2]:
            if fold_key(name) != fold_key(target):
                queries.append(f'"{name}"')

    seen = set()
    stable = []
    for query in queries:
        key = fold_key(query)
        if key not in seen:
            seen.add(key)
            stable.append(query)
    return stable


def classify_url(url: str) -> tuple[str, str]:
    """คืน (source_type, platform) แบบหยาบจาก URL"""
    low = url.casefold()
    platforms = {
        "github.com": "github",
        "gitlab.com": "gitlab",
        "reddit.com": "reddit",
        "t.me": "telegram",
        "keybase.io": "keybase",
        "twitch.tv": "twitch",
        "medium.com": "medium",
        "dev.to": "devto",
        "npmjs.com": "npm",
        "pinterest.": "pinterest",
        "x.com": "x",
        "twitter.com": "x",
        "instagram.com": "instagram",
        "facebook.com": "facebook",
        "pantip.com": "pantip",
        "linkedin.com": "linkedin",
    }
    if "pantip.com" in low and "/topic/" in low:
        return "post", "pantip"
    for marker, platform in platforms.items():
        if marker in low:
            return "profile", platform
    if any(marker in low for marker in ("/post", "/status/", "/p/", "/photos/", "/blog/")):
        return "post", ""
    return "page", ""
