"""Multi-Platform OSINT Scanner

หลักการ: ทุกโปรไฟล์ต้องจำแนกเป็น found / not_found / blocked / unknown
ห้ามถือว่า HTTP 200 เท่ากับ "พบบัญชี" เพราะหลายแพลตฟอร์มคืน 200 ให้ทุกชื่อ
"""

import asyncio
import time
from dataclasses import dataclass

import httpx

from .tools.base import USER_AGENT

TIMEOUT = 10.0
MAX_CONCURRENCY = 8
MAX_BODY_CHARS = 200_000


@dataclass(frozen=True)
class Platform:
    name: str
    url_template: str
    found_marker: str = ""
    not_found_marker: str = ""
    identifier_type: str = "username"
    api_url_template: str = ""
    found_marker_required: bool = False


PLATFORMS = [
    # Social — ส่วนใหญ่คืน 200 ทุกชื่อ ต้องดู marker
    Platform("Facebook", "https://www.facebook.com/{identifier}", not_found_marker="Page Not Found"),
    Platform("Instagram", "https://www.instagram.com/{identifier}/", not_found_marker="Sorry, this page isn't available"),
    Platform("Twitter/X", "https://x.com/{identifier}"),
    Platform("TikTok", "https://www.tiktok.com/@{identifier}", not_found_marker="Couldn't find this account"),
    Platform("LinkedIn", "https://www.linkedin.com/in/{identifier}"),
    Platform("YouTube", "https://www.youtube.com/@{identifier}", not_found_marker="404"),
    Platform("Snapchat", "https://www.snapchat.com/add/{identifier}"),
    Platform(
        "Telegram",
        "https://t.me/{identifier}",
        found_marker="tgme_page_title",
        found_marker_required=True,
    ),
    Platform(
        "Reddit",
        "https://www.reddit.com/user/{identifier}",
        api_url_template="https://www.reddit.com/user/{identifier}/about.json",
    ),
    Platform("Pinterest", "https://www.pinterest.com/{identifier}/"),
    Platform("Tumblr", "https://{identifier}.tumblr.com"),
    Platform("Discord", "https://discord.com/users/{identifier}"),

    # Developer
    Platform("GitHub", "https://github.com/{identifier}", found_marker='itemprop="name"'),
    Platform(
        "GitLab",
        "https://gitlab.com/{identifier}",
        api_url_template="https://gitlab.com/api/v4/users?username={identifier}",
    ),
    Platform("Bitbucket", "https://bitbucket.org/{identifier}"),
    Platform("Stack Overflow", "https://stackoverflow.com/users/{identifier}"),
    Platform("HackerRank", "https://www.hackerrank.com/{identifier}"),
    Platform("LeetCode", "https://leetcode.com/{identifier}"),
    Platform("Kaggle", "https://www.kaggle.com/{identifier}"),
    Platform("CodePen", "https://codepen.io/{identifier}"),

    # Forums & communities
    Platform("Pantip", "https://pantip.com/profile/{identifier}"),
    Platform("Medium", "https://medium.com/@{identifier}"),
    Platform("DeviantArt", "https://www.deviantart.com/{identifier}"),
    Platform("Behance", "https://www.behance.net/{identifier}"),
    Platform("Dribbble", "https://dribbble.com/{identifier}"),
    Platform("Flickr", "https://www.flickr.com/people/{identifier}"),

    # Gaming
    Platform("Twitch", "https://www.twitch.tv/{identifier}"),
    Platform("Steam", "https://steamcommunity.com/id/{identifier}"),
    Platform("Xbox Live", "https://account.xbox.com/en-us/profile?gamertag={identifier}"),
    Platform("PlayStation", "https://psnprofiles.com/{identifier}"),

    # Business
    Platform("AngelList", "https://angel.co/{identifier}"),
    Platform("Crunchbase", "https://www.crunchbase.com/person/{identifier}"),

    # Phone
    Platform("WhatsApp", "https://wa.me/{identifier}", found_marker="action-send", identifier_type="phone"),
]


@dataclass
class PlatformResult:
    platform: str
    url: str
    status: str  # found | not_found | blocked | unknown | error
    http_status: int = 0
    detail: str = ""
    elapsed_ms: int = 0


def _classify(platform: Platform, status_code: int, body: str) -> str:
    if status_code in (404, 410):
        return "not_found"
    if status_code in (401, 403, 429, 999):
        return "blocked"
    if status_code >= 400:
        return "error"
    if status_code != 200:
        return "unknown"

    lowered = body.lower()
    if platform.not_found_marker and platform.not_found_marker.lower() in lowered:
        return "not_found"
    if platform.found_marker:
        if platform.found_marker.lower() in lowered:
            return "found"
        return "not_found" if platform.found_marker_required else "unknown"
    return "unknown"


async def _check(
    client: httpx.AsyncClient, platform: Platform, identifier: str, semaphore: asyncio.Semaphore
) -> PlatformResult:
    from urllib.parse import quote_plus

    profile_url = platform.url_template.format(identifier=quote_plus(identifier))
    request_url = (
        platform.api_url_template.format(identifier=quote_plus(identifier))
        if platform.api_url_template
        else profile_url
    )
    started = time.monotonic()
    async with semaphore:
        try:
            response = await client.get(request_url)
            body = response.text[:MAX_BODY_CHARS]
            if platform.api_url_template:
                if response.status_code == 404 or body.strip() == "[]":
                    status = "not_found"
                elif response.status_code == 200:
                    status = "found"
                elif response.status_code in (401, 403, 429, 999):
                    status = "blocked"
                else:
                    status = "unknown"
            else:
                status = _classify(platform, response.status_code, body)
            http_status = response.status_code
        except httpx.HTTPError as exc:
            status = "error"
            http_status = 0
            body = type(exc).__name__
    return PlatformResult(
        platform=platform.name,
        url=profile_url,
        status=status,
        http_status=http_status,
        detail="" if status in ("found", "not_found") else body[:120],
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


async def scan(identifier: str, identifier_type: str = "username") -> dict:
    targets = [p for p in PLATFORMS if p.identifier_type == identifier_type]
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    started = time.monotonic()

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "th,en;q=0.8"},
    ) as client:
        results = await asyncio.gather(*(_check(client, p, identifier, semaphore) for p in targets))

    counts = {key: 0 for key in ("found", "not_found", "blocked", "unknown", "error")}
    for item in results:
        counts[item.status] += 1

    return {
        "identifier": identifier,
        "identifier_type": identifier_type,
        "results": results,
        "counts": counts,
        "scan_time": time.monotonic() - started,
    }


def scan_sync(identifier: str, identifier_type: str = "username") -> dict:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(scan(identifier, identifier_type))

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(scan(identifier, identifier_type))).result()


def format_scan_results(results: dict) -> str:
    lines = [f"🔍 สแกน {results['identifier_type']}: {results['identifier']}"]
    counts = results["counts"]
    lines.append(
        f"พบบัญชี {counts['found']} · ไม่พบ {counts['not_found']} · "
        f"ตรวจไม่ได้ {counts['blocked']} · ยังสรุปไม่ได้ {counts['unknown']} · error {counts['error']}"
    )
    lines.append("")

    labels = [
        ("found", "✅ พบโปรไฟล์"),
        ("unknown", "❔ เปิดได้แต่ยืนยันไม่ได้"),
        ("blocked", "🚫 ถูกบล็อก/ต้องล็อกอิน"),
        ("error", "⚠️ เรียกไม่สำเร็จ"),
    ]
    for status, header in labels:
        group = [r for r in results["results"] if r.status == status]
        if not group:
            continue
        lines.append(header + ":")
        for item in group:
            lines.append(f"  - {item.platform}: {item.url}")
        lines.append("")

    lines.append(f"เวลาที่ใช้: {results['scan_time']:.1f} วินาที")
    if counts["unknown"]:
        lines.append(
            "หมายเหตุ: สถานะ 'ยืนยันไม่ได้' ไม่ใช่หลักฐานว่าไม่มีบัญชี — "
            "แพลตฟอร์มกลุ่มนี้ตอบหน้าเดียวกันทุกชื่อ ต้องเปิดดูด้วย fetch_page เอง"
        )
    return "\n".join(lines)
