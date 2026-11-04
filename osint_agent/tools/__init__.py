"""คลังเครื่องมือของ agent — package ย่อย แยกตามหมวด

execute_tool() คืน dict เสมอ: {"output": str, "images": [{"media_type", "data"}, ...]}
ภาพที่แนบมาจะถูกส่งเข้าโมเดลใน tool_result ทำให้ agent "เห็น" รูปในหน้าเว็บได้

หมวด:
- search: web_search, sherlock_username, extract_entities
- http: fetch_page (SSRF-guarded)
- phone: phone_info, scan_phone_advanced, verify_official
- breach: breach_check
- analysis: scan_platforms, compare_avatars, correlate_stylometry,
            username_correlation, email_harvest, identity_candidate, darkweb_monitor
"""

from .base import (  # noqa: F401 — re-export เพื่อความเข้ากันได้กับโค้ด/เทสต์เดิม
    EMAIL_ONLY_RE,
    EMAIL_RE,
    FETCH_TIMEOUT,
    HANDLE_RE,
    MAX_IMAGES,
    PHONE_RE,
    URL_RE,
    USER_AGENT,
    USERNAME_RE,
    plain,
)
from .http import (  # noqa: F401
    RATE_LIMITER,
    DomainRateLimiter,
    UnsafeURLError,
    _check_url,
    _is_public_host,
    fetch_page_schema,
    run_fetch,
    safe_get,
)
from .registry import TOOLS, build_tool_list, execute_tool  # noqa: F401
