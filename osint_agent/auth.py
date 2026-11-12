"""การพิสูจน์ตัวตนและกำหนดสิทธิ์ (demo, ข้อมูลผู้ใช้จำลอง)

- รหัสผ่านเก็บเป็น PBKDF2-SHA256 พร้อม salt แบบสุ่ม
- session token เซ็นด้วย HMAC-SHA256 และมีวันหมดอายุ
- แยกบทบาท viewer / analyst / admin ตามหลัก least privilege
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_USERS_FILE = ROOT / "config" / "users.json"
SECRET_FILE = ROOT / "audit" / ".secret_key"
TOKEN_TTL = 8 * 3600
PBKDF2_ITERATIONS = 200_000
MAX_FAILURES = 5
FAILURE_WINDOW = 300
LOCK_SECONDS = 60

ROLES = ("viewer", "analyst", "admin")
PERMISSIONS = {
    "viewer": {"read", "export"},
    "analyst": {"read", "export", "investigate", "review", "cancel"},
    "admin": {"read", "export", "investigate", "review", "cancel", "manage_users", "settings"},
}

_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def users_file() -> Path:
    return Path(os.environ.get("OSINT_USERS_FILE") or DEFAULT_USERS_FILE)


def hash_password(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(candidate.hex(), digest)
    except (ValueError, AttributeError):
        return False


def load_users() -> list[dict]:
    inline = os.environ.get("OSINT_USERS")
    if inline:
        try:
            payload = json.loads(inline)
            return payload.get("users", []) if isinstance(payload, dict) else payload
        except json.JSONDecodeError:
            return []
    path = users_file()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload.get("users", []) if isinstance(payload, dict) else payload


def public_user(user: dict) -> dict:
    return {
        "username": user.get("username", ""),
        "name": user.get("name") or user.get("username", ""),
        "role": user.get("role", "viewer"),
        "unit": user.get("unit", ""),
    }


def find_user(username: str) -> dict | None:
    username = (username or "").strip().lower()
    return next((u for u in load_users() if str(u.get("username", "")).lower() == username), None)


def _locked(username: str) -> bool:
    now = time.time()
    with _lock:
        attempts = [t for t in _failures.get(username, []) if now - t < FAILURE_WINDOW]
        _failures[username] = attempts
        if len(attempts) < MAX_FAILURES:
            return False
        return now - attempts[-MAX_FAILURES] < LOCK_SECONDS


def _record_failure(username: str) -> None:
    with _lock:
        _failures.setdefault(username, []).append(time.time())


def authenticate(username: str, password: str) -> dict | None:
    user = find_user(username)
    key = (username or "").strip().lower()
    if not user or not user.get("active", True) or _locked(key):
        return None
    if not verify_password(password, str(user.get("password_hash", ""))):
        _record_failure(key)
        return None
    with _lock:
        _failures.pop(key, None)
    return public_user(user)


def has_permission(user: dict | None, permission: str) -> bool:
    if not user:
        return False
    return permission in PERMISSIONS.get(user.get("role", "viewer"), set())


def _secret() -> bytes:
    env = os.environ.get("OSINT_SECRET_KEY")
    if env:
        return env.encode("utf-8")
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_bytes()
    value = secrets.token_bytes(32)
    SECRET_FILE.write_bytes(value)
    try:
        SECRET_FILE.chmod(0o600)
    except OSError:
        pass
    return value


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_token(user: dict, ttl: int = TOKEN_TTL) -> str:
    body = {
        "sub": user["username"],
        "name": user.get("name", ""),
        "role": user.get("role", "viewer"),
        "unit": user.get("unit", ""),
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
        "jti": secrets.token_hex(8),
    }
    payload = _b64(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_token(token: str) -> dict | None:
    if not token or token.count(".") != 1:
        return None
    payload, signature = token.split(".", 1)
    expected = _b64(hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        body = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(body.get("exp", 0)) < time.time():
        return None
    user = find_user(str(body.get("sub", "")))
    if not user or not user.get("active", True):
        return None
    current = public_user(user)
    current["exp"] = body["exp"]
    current["jti"] = body.get("jti", "")
    return current


def list_public_users() -> list[dict]:
    return [public_user(user) for user in load_users()]
