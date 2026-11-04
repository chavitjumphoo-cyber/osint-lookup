"""ตัวเก็บข้อมูล: ค้นเว็บ, เปิดหน้า, และดึงโปรไฟล์จาก scanner ที่ vendor ไว้"""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from urllib.parse import parse_qs, urlparse

from ..core.evidence import classify_status, output_hash
from ..services import browser, search_engines
from ..services.trust_anchor import SCANNER_CLASSES
from .artifacts import Artifact
from .normalizers import clean, snippet
from .pivots import classify_url

PROFILE_HOSTS = {
    "github", "gitlab", "reddit", "telegram", "keybase", "twitch", "medium",
    "devto", "npm", "pinterest", "x", "instagram", "facebook", "pantip", "linkedin",
}


def _artifact(source_url: str, source_type: str, source_tool: str, content: str, **kwargs) -> Artifact:
    platform = kwargs.pop("platform", "")
    status = kwargs.pop("status", "ok")
    result = kwargs.pop("result", content)
    return Artifact(
        source_url=source_url,
        source_type=source_type,
        source_tool=source_tool,
        platform=platform,
        content=content,
        status=status,
        output_hash=output_hash(source_tool, source_url, status, result),
        **kwargs,
    )


def search(query: str, limit: int = 8) -> list[Artifact]:
    """ค้นและคืน artifact ผลค้น (ยังไม่ใช่น่าเชื่อถือ — Unverified)"""
    payload = search_engines.search(query, limit=limit)
    artifacts = []
    for item in payload["results"]:
        source_type, platform = classify_url(item["url"])
        artifacts.append(
            _artifact(
                source_url=item["url"],
                source_type="search_result",
                source_tool=f"search:{item['engine']}",
                content=snippet(f"{item['title']}\n{item['snippet']}"),
                platform=platform,
                title=item["title"],
                query=query,
                confidence="Unverified",
                result=f"{item['title']}|{item['snippet']}",
            )
        )
    return artifacts


def rank_result(artifact: dict) -> float:
    score = 0.3
    if artifact.get("platform") in PROFILE_HOSTS:
        score += 0.5
    if artifact.get("source_type") == "profile":
        score += 0.2
    text = f"{artifact.get('title', '')} {artifact.get('content', '')}".lower()
    for word in ("about", "bio", "profile", "contact", "resume", "มิจฉาชีพ", "scam", "โกง"):
        if word in text:
            score += 0.05
    host = urlparse(artifact.get("source_url", "")).hostname or ""
    if any(bad in host for bad in ("google.", "bing.", "yahoo.", "duckduckgo.")):
        score -= 0.3
    return round(min(1.0, score), 3)


def resolve_redirect(url: str) -> str:
    """ถอด DuckDuckGo redirect (uddg=) ให้ได้ URL จริง"""
    parsed = urlparse(url)
    if "duckduckgo.com" in (parsed.hostname or "") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return target[0]
    return url


def fetch(url: str) -> Artifact:
    url = resolve_redirect(url)
    source_type, platform = classify_url(url)
    try:
        page = browser.fetch_json(url, timeout=25)
    except browser.BrowserError as exc:
        return _artifact(
            url, "page", "moli_fetch", "", status="blocked", platform=platform,
            result=str(exc), confidence="Unverified",
        )
    if page.status >= 400:
        return _artifact(
            url, "page", "moli_fetch", "", status="blocked", platform=platform,
            result=f"HTTP {page.status}", confidence="Unverified",
        )
    if source_type == "profile" or platform in PROFILE_HOSTS:
        source_type = "profile"
    if source_type == "profile":
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page.html, "html.parser")

        def meta(name: str) -> str:
            tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
            return (tag.get("content") or "").strip() if tag else ""

        title = meta("og:title")
        bio = meta("og:description") or meta("description")
        body = clean(soup.get_text("\n", strip=True))[:4000]
        content = "\n".join(part for part in (title, bio, body) if part)
        return _artifact(
            url, "profile", "moli_fetch", content[:5000],
            platform=platform, title=title, confidence="Probable",
            metadata={"avatar": meta("og:image"), "bio": bio},
        )

    text = clean(page.html)
    return _artifact(
        url, source_type, "moli_fetch", text[:12000], platform=platform,
        title=page.title, confidence="Unverified",
    )


def fetch_many(urls: list[str], limit: int = 5) -> list[Artifact]:
    artifacts = []
    for url in urls[:limit]:
        artifact = fetch(url)
        artifacts.append(artifact)
    return artifacts


def _profile_to_artifact(profile) -> Artifact | None:
    meta = profile.metadata if isinstance(profile.metadata, dict) else {}
    name = next((meta.get(k) for k in ("name", "display_name", "og_title") if meta.get(k)), "")
    parts = [
        name,
        profile.bio or meta.get("bio") or "",
        meta.get("company") or "",
        meta.get("location") or "",
        meta.get("blog") or meta.get("website") or "",
        meta.get("email") or "",
        f"joined {meta.get('created_at')}" if meta.get("created_at") else "",
        f"{meta.get('followers')} followers" if meta.get("followers") else "",
    ]
    content = "\n".join(part for part in parts if part)
    return _artifact(
        profile.url,
        "profile",
        f"scanner:{profile.network_name}",
        content or profile.bio or "",
        platform=profile.network_name,
        title=name,
        author=profile.username,
        confidence="Probable",
        result=content,
    )


async def _scan_one(cls, username: str, settings):
    try:
        result = await cls(settings).scan(username)
    except Exception:  # noqa: BLE001
        return []
    return result if isinstance(result, list) else [result]


def scan_profiles(username: str, timeout: float = 45.0) -> list[Artifact]:
    from vendor._compat import settings_from_project

    settings = settings_from_project()
    classes = set(SCANNER_CLASSES.values())

    async def main():
        batches = await asyncio.gather(*(_scan_one(cls, username, settings) for cls in classes))
        return [item for batch in batches for item in batch if item and item.exists]

    try:
        profiles = asyncio.run(main())
    except RuntimeError:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            profiles = pool.submit(lambda: asyncio.run(main())).result()
    artifacts = []
    for profile in profiles:
        artifact = _profile_to_artifact(profile)
        if artifact and artifact.content:
            artifacts.append(artifact)
    return artifacts


def probe_platforms(username: str, include_unknown: bool = True) -> list[Artifact]:
    """ตรวจ username ข้ามแพลตฟอร์ม แล้วคืน artifact สำหรับ found/unknown"""
    from .. import platform_scanner

    try:
        results = platform_scanner.scan_sync(username)
    except Exception:  # noqa: BLE001
        return []
    wanted = {"found", "unknown"} if include_unknown else {"found"}
    artifacts = []
    for item in results["results"]:
        if item.status not in wanted:
            continue
        source_type, platform = classify_url(item.url)
        artifacts.append(
            _artifact(
                item.url,
                "profile" if source_type == "profile" else "page",
                f"probe:{item.platform}",
                "",
                platform=platform or item.platform.lower(),
                status=item.status,
                result=item.status,
                confidence="Unverified",
            )
        )
    return artifacts


def artifact_status_from_text(text: str) -> str:
    return classify_status(text)


def username_from_url(url: str) -> str | None:
    path = urlparse(url).path.strip("/").split("/")
    if not path:
        return None
    candidate = path[-1].lstrip("@")
    return candidate if re.fullmatch(r"[A-Za-z0-9._-]{2,64}", candidate or "") else None
