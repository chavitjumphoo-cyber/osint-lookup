"""Trust anchors — ใช้บัญชีที่ผู้ใช้ยืนยันแล้วเป็นเส้นอ้างอิง แล้วตัด namesake ทิ้ง"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from vendor.osint_d2.adapters import osint_sources
from vendor.osint_d2.core.domain.models import SocialProfile
from vendor.osint_d2.services import trust_anchor as vendor

from ..tools.base import USERNAME_RE
from .tool_runner import run_tool

SCANNER_CLASSES = {
    name.removesuffix("Scanner").lower(): getattr(osint_sources, name)
    for name in dir(osint_sources)
    if name.endswith("Scanner")
}
SCANNER_CLASSES.update({"x": osint_sources.XScanner, "twitter": osint_sources.XScanner})


@dataclass
class TrustResult:
    kept: list[SocialProfile] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    reference_names: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"ยืนยันโปรไฟล์ที่สอดคล้อง anchor: {len(self.kept)}",
            f"ตัดโปรไฟล์ที่ขัดแย้ง: {len(self.dropped)}",
        ]
        for item in self.dropped:
            lines.append(f"- ตัด {item['url']} ({'; '.join(item['reasons'])})")
        return "\n".join(lines)


def _parse(raw: str) -> vendor.TrustAnchor:
    return vendor.TrustAnchor.parse(raw.strip())


async def _scan_anchor(anchor: vendor.TrustAnchor, settings) -> SocialProfile | None:
    cls = SCANNER_CLASSES.get(anchor.network)
    if not cls:
        return None
    try:
        profile = await cls(settings).scan(anchor.username)
    except Exception:  # noqa: BLE001 — anchor ตัวเดียวพังไม่ควรล้มทั้งงาน
        return None
    if isinstance(profile, list):
        profile = profile[0] if profile else None
    return profile


async def _scan_all(username: str, settings) -> list[SocialProfile]:
    async def one(cls):
        try:
            result = await cls(settings).scan(username)
        except Exception:  # noqa: BLE001
            return []
        return result if isinstance(result, list) else [result]

    batches = await asyncio.gather(*(one(cls) for cls in set(SCANNER_CLASSES.values())))
    return [profile for batch in batches for profile in batch if profile and profile.exists]


def apply_trust(target: str, anchors: list[str]) -> TrustResult:
    """สแกนหาบัญชีที่ตรงกับ anchor แล้วตรวจโปรไฟล์อื่นทั้งหมด"""
    parsed = []
    for raw in anchors:
        try:
            parsed.append(_parse(raw))
        except ValueError:
            continue

    if not parsed or not USERNAME_RE.match(target):
        return TrustResult(errors=["anchor หรือ target ไม่ถูกต้อง"] if anchors else [])

    from vendor._compat import settings_from_project

    settings = settings_from_project()

    async def main() -> TrustResult:
        anchor_profiles = [p for p in await asyncio.gather(*(_scan_anchor(a, settings) for a in parsed)) if p]
        reference = vendor.build_reference_from_profiles(anchor_profiles, parsed)
        found = await _scan_all(target, settings)

        result = TrustResult(reference_names=sorted(reference.names))
        for profile in found:
            verdict = vendor.verify_profile(profile, reference)
            if verdict.verified:
                result.kept.append(profile)
            else:
                result.dropped.append({"url": profile.url, "reasons": verdict.reasons})
        return result

    try:
        return asyncio.run(main())
    except RuntimeError:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(main())).result()


def anchors_evidence(anchors: list[str]) -> str:
    return "\n".join(f"- {anchor}" for anchor in anchors)


__all__ = ["TrustResult", "apply_trust", "anchors_evidence", "run_tool"]
