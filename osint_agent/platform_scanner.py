"""
Multi-Platform OSINT Scanner — Inspired by SYNINT + osint-d2
รวม 30+ แพลตฟอร์มสำหรับค้นหา username, email, phone
"""

import re
import time
import requests
from typing import Dict, List, Optional
from urllib.parse import quote_plus

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 10


class PlatformScanner:
    """Base class สำหรับ platform scanner"""

    def __init__(self, name: str, check_url: str, identifier_type: str = "username"):
        self.name = name
        self.check_url = check_url
        self.identifier_type = identifier_type

    def check(self, identifier: str) -> Optional[Dict]:
        """
        ตรวจสอบว่า identifier มีอยู่ในแพลตฟอร์มนี้หรือไม่
        Return: {"platform": str, "url": str, "found": bool, "data": dict} หรือ None
        """
        try:
            url = self.check_url.format(identifier=quote_plus(identifier))
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)

            # เช็คว่าโปรไฟล์มีจริง
            found = self._check_found(response)

            if found:
                return {
                    "platform": self.name,
                    "url": url,
                    "found": True,
                    "data": self._extract_data(response),
                }
            return None

        except Exception as e:
            return None

    def _check_found(self, response) -> bool:
        """Override ใน subclass — ตรวจว่าโปรไฟล์มีจริง"""
        # Default: status 200 = found
        return response.status_code == 200

    def _extract_data(self, response) -> Dict:
        """Override ใน subclass — สกัดข้อมูลจากหน้า"""
        return {}


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


def scan_multi_platform(identifier: str, identifier_type: str = "username") -> List[Dict]:
    """
    สแกน identifier ข้ามหลายแพลตฟอร์ม

    Args:
        identifier: username, email, หรือ phone
        identifier_type: "username", "email", "phone"

    Returns:
        List[{"platform": str, "url": str, "found": bool, "data": dict}]
    """
    results = []

    # กรอง platforms ตาม identifier_type
    filtered = [p for p in PLATFORMS if p.identifier_type == identifier_type]

    for platform in filtered:
        result = platform.check(identifier)
        if result:
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
    results = scan_multi_platform(username, "username")

    return {
        "username": username,
        "platforms_found": results,
        "total_found": len(results),
        "scan_time": time.time() - start,
    }


def format_scan_results(results: Dict) -> str:
    """จัดรูปแบบผลลัพธ์เป็น text สำหรับ agent"""
    output = f"🔍 Username Scan: {results['username']}\n\n"
    output += f"✓ พบบน {results['total_found']} แพลตฟอร์ม:\n\n"

    for r in results["platforms_found"]:
        output += f"  • {r['platform']}: {r['url']}\n"

    if results["total_found"] == 0:
        output += "ไม่พบโปรไฟล์ในแพลตฟอร์มที่ตรวจสอบ\n"

    output += f"\nเวลาที่ใช้: {results['scan_time']:.1f} วินาที"

    return output
