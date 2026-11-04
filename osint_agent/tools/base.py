"""ค่าคงที่และตัวช่วยกลางของชั้น tool"""

import re

FETCH_TIMEOUT = 15
IMAGE_TIMEOUT = 10
FETCH_MAX_CHARS = 12000
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 1_500_000
SHERLOCK_TIMEOUT = 180
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Research/1.0"

IMAGE_MEDIA_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}

# ชื่อผู้ใช้ที่ยอมให้ส่งเข้า sherlock — กันการแทรก argument (เช่น "--json /etc/passwd")
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

PHONE_RE = re.compile(r"(?<!\d)(?:\+66|0)[\d\-\s]{8,12}\d(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_.]{3,30}")
ACCOUNT_RE = re.compile(r"(?<!\d)\d{3}[-\s]?\d[-\s]?\d{5}[-\s]?\d(?!\d)")
EMAIL_ONLY_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def plain(text: str) -> dict:
    return {"output": text, "images": []}


def tool_error(name: str, exc: Exception) -> dict:
    return plain(f"เครื่องมือ '{name}' เกิดข้อผิดพลาด: {type(exc).__name__}: {exc}")
