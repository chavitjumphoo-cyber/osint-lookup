"""
Multi-Platform OSINT Scanner — Inspired by SYNINT + osint-d2
รวม 30+ แพลตฟอร์มสำหรับค้นหา username, email, phone
"""

import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .network import UnsafeURLError, safe_get

TIMEOUT = 10


def _same_profile_url(left: str, right: str) -> bool:
    def key(url):
        parsed = urlparse(url)
        return (
            (parsed.hostname or "").lower().removeprefix("www."),
            unquote(parsed.path).rstrip("/").lower(),
            parsed.query,
        )
    return key(left) == key(right)


class PlatformScanner:
    """Check profile evidence; blocked and ambiguous pages remain unverified."""

    def __init__(self, name: str, check_url: str, identifier_type: str = "username"):
        self.name = name
        self.check_url = check_url
        self.identifier_type = identifier_type

    def check(self, identifier: str) -> Optional[Dict]:
        """Return a confirmed/unknown result, or None for an explicit not-found response."""
        url = self.check_url.format(identifier=quote_plus(identifier))
        result = {"platform": self.name, "url": url, "found": False,
                  "status": "unknown", "data": {}}
        try:
            response = safe_get(url, timeout=TIMEOUT)
            try:
                if response.status_code in (404, 410):
                    return None
                final_url = response.url or url
                if response.status_code != 200 or not _same_profile_url(url, final_url):
                    result["reason"] = "ถูกบล็อก เปลี่ยนหน้า หรือต้องเข้าสู่ระบบ"
                    return result
                if self._check_found(response):
                    result.update(found=True, status="found", data=self._extract_data(response))
                else:
                    result["reason"] = "ยังไม่มีหลักฐานในหน้าที่ใช้ยืนยันโปรไฟล์"
                return result
            finally:
                response.close()
        except (requests.RequestException, UnsafeURLError, ValueError):
            result["reason"] = "เปิดหน้าเว็บเพื่อตรวจสอบไม่ได้"
            return result

    def _check_found(self, response) -> bool:
        """Require profile metadata tied to the requested profile, rather than HTTP 200."""
        if response.status_code != 200:
            return False
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
        if re.search(r"log[ -]?in|sign[ -]?in|not found|doesn.t exist|captcha|access denied", title):
            return False
        if soup.select_one('form[action*="login"], form[action*="signin"]'):
            return False
        metadata = {
            str(tag.get("property") or tag.get("name") or "").lower(): str(tag.get("content", ""))
            for tag in soup.find_all("meta")
        }
        parsed = urlparse(response.url)
        username = unquote(parsed.path).rstrip("/").split("/")[-1].lstrip("@").lower()
        for name in ("profile:username", "octolytics-dimension-user_login"):
            profile_username = metadata.get(name, "").strip().lstrip("@").lower()
            if profile_username:
                return bool(username) and profile_username == username
        return (
            metadata.get("og:type", "").lower() == "profile"
            and bool(metadata.get("og:url"))
            and _same_profile_url(metadata["og:url"], response.url)
        )

    def _extract_data(self, response) -> Dict:
        return {"evidence": "profile metadata", "checked_url": response.url}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 30+ Platform Scanners
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PLATFORMS = [
    # Social Media
    PlatformScanner("Facebook", "https://www.facebook.com/{identifier}"),
    PlatformScanner("Instagram", "https://www.instagram.com/{identifier}/"),
    PlatformScanner("Twitter/X", "https://x.com/{identifier}"),
    PlatformScanner("TikTok", "https://www.tiktok.com/@{identifier}"),
    PlatformScanner("LinkedIn", "https://www.linkedin.com/in/{identifier}"),
    PlatformScanner("YouTube", "https://www.youtube.com/@{identifier}"),
    PlatformScanner("Snapchat", "https://www.snapchat.com/add/{identifier}"),
    PlatformScanner("Telegram", "https://t.me/{identifier}"),
    PlatformScanner("WhatsApp", "https://wa.me/{identifier}", "phone"),
    PlatformScanner("Discord", "https://discord.com/users/{identifier}"),
    PlatformScanner("Reddit", "https://www.reddit.com/user/{identifier}"),
    PlatformScanner("Pinterest", "https://www.pinterest.com/{identifier}/"),
    PlatformScanner("Tumblr", "https://{identifier}.tumblr.com"),

    # Developer Platforms
    PlatformScanner("GitHub", "https://github.com/{identifier}"),
    PlatformScanner("GitLab", "https://gitlab.com/{identifier}"),
    PlatformScanner("Bitbucket", "https://bitbucket.org/{identifier}"),
    PlatformScanner("Stack Overflow", "https://stackoverflow.com/users/{identifier}"),
    PlatformScanner("HackerRank", "https://www.hackerrank.com/{identifier}"),
    PlatformScanner("LeetCode", "https://leetcode.com/{identifier}"),
    PlatformScanner("Kaggle", "https://www.kaggle.com/{identifier}"),
    PlatformScanner("CodePen", "https://codepen.io/{identifier}"),

    # Forums & Communities
    PlatformScanner("Pantip", "https://pantip.com/profile/{identifier}"),
    PlatformScanner("Medium", "https://medium.com/@{identifier}"),
    PlatformScanner("DeviantArt", "https://www.deviantart.com/{identifier}"),
    PlatformScanner("Behance", "https://www.behance.net/{identifier}"),
    PlatformScanner("Dribbble", "https://dribbble.com/{identifier}"),
    PlatformScanner("Flickr", "https://www.flickr.com/people/{identifier}"),

    # Gaming
    PlatformScanner("Twitch", "https://www.twitch.tv/{identifier}"),
    PlatformScanner("Steam", "https://steamcommunity.com/id/{identifier}"),
    PlatformScanner("Xbox Live", "https://account.xbox.com/en-us/profile?gamertag={identifier}"),
    PlatformScanner("PlayStation", "https://psnprofiles.com/{identifier}"),

    # Business
    PlatformScanner("AngelList", "https://angel.co/{identifier}"),
    PlatformScanner("Crunchbase", "https://www.crunchbase.com/person/{identifier}"),
]


def scan_multi_platform(
    identifier: str, identifier_type: str = "username", include_unknown: bool = False
) -> List[Dict]:
    """
    สแกน identifier ข้ามหลายแพลตฟอร์ม

    Args:
        identifier: username, email, หรือ phone
        identifier_type: "username", "email", "phone"

    Returns:
        List[{"platform": str, "url": str, "found": bool, "data": dict}]
    """
    if not identifier.strip():
        raise ValueError("กรุณาระบุ identifier")
    results = []

    # กรอง platforms ตาม identifier_type
    filtered = [p for p in PLATFORMS if p.identifier_type == identifier_type]

    for platform in filtered:
        result = platform.check(identifier)
        if result and (result["found"] or include_unknown):
            results.append(result)
        # Delay เพื่อไม่ให้โดนบล็อก
        time.sleep(0.5)

    return results


def scan_username_advanced(username: str) -> Dict:
    """
    สแกน username แบบ advanced — ใช้แทน sherlock สำหรับ real-time scanning

    Returns:
        {
            "username": str,
            "platforms_found": List[Dict],
            "total_found": int,
            "scan_time": float,
        }
    """
    start = time.time()
    checked = scan_multi_platform(username, "username", include_unknown=True)
    results = [result for result in checked if result["found"]]
    unknown = [result for result in checked if not result["found"]]

    return {
        "username": username,
        "platforms_found": results,
        "total_found": len(results),
        "platforms_unknown": unknown,
        "total_unknown": len(unknown),
        "scan_time": time.time() - start,
    }


def format_scan_results(results: Dict) -> str:
    """จัดรูปแบบผลลัพธ์เป็น text สำหรับ agent"""
    output = f"🔍 Username Scan: {results['username']}\n\n"
    output += f"✓ ยืนยันโปรไฟล์ได้บน {results['total_found']} แพลตฟอร์ม:\n\n"

    for r in results["platforms_found"]:
        output += f"  • {r['platform']}: {r['url']}\n"

    if results["total_found"] == 0:
        output += "ยังไม่มีโปรไฟล์ที่ยืนยันได้\n"

    unknown = results.get("platforms_unknown", [])
    if unknown:
        output += "\n⚠ ยังยืนยันไม่ได้ (ห้ามสรุปว่ามีหรือไม่มีบัญชี):\n"
        for result in unknown:
            output += f"  • {result['platform']}: {result['url']} — {result.get('reason', 'ต้องตรวจสอบเพิ่ม')}\n"
    output += "\nการพบ username เดียวกันไม่ได้ยืนยันว่าเป็นบุคคลเดียวกัน\n"
    output += f"\nเวลาที่ใช้: {results['scan_time']:.1f} วินาที"

    return output
