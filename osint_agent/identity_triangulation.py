"""
Identity Triangulation Engine — Inspired by osint-d2
เชื่อมโยง identities จากหลาย sources และสร้าง confidence score
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import re


@dataclass
class Identity:
    """ตัวตน (Identity) ที่พบจากการสืบสวน"""

    # Core identifiers
    names: Set[str] = field(default_factory=set)
    usernames: Set[str] = field(default_factory=set)
    emails: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)

    # Social profiles
    profiles: Dict[str, str] = field(default_factory=dict)  # platform -> url

    # Metadata
    locations: Set[str] = field(default_factory=set)
    organizations: Set[str] = field(default_factory=set)
    interests: Set[str] = field(default_factory=set)

    # Avatar/Images
    avatar_urls: Set[str] = field(default_factory=set)

    # Trust & Evidence
    sources: List[Dict] = field(default_factory=list)  # [{source, data, timestamp, confidence}]
    confidence_score: float = 0.0

    # Timestamps
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class IdentityTriangulator:
    """
    Identity Triangulation Engine
    เชื่อมโยง identities จากหลาย sources ด้วย trust anchors และ confidence scoring
    """

    def __init__(self):
        self.identities: List[Identity] = []

    def add_evidence(
        self,
        source: str,
        data: Dict,
        confidence: float = 0.5
    ) -> Identity:
        """
        เพิ่มหลักฐานจาก source และสร้าง/อัปเดต identity

        Args:
            source: แหล่งที่มา เช่น "sherlock", "google_search", "phone_scan"
            data: ข้อมูลที่พบ {names, usernames, emails, phones, ...}
            confidence: ความมั่นใจ 0.0-1.0

        Returns:
            Identity object ที่สร้าง/อัปเดต
        """
        # หา identity ที่มีอยู่แล้วหรือสร้างใหม่
        identity = self._find_or_create_identity(data)

        # เพิ่มข้อมูลจาก data
        if "names" in data:
            identity.names.update(self._normalize_list(data["names"]))
        if "usernames" in data:
            identity.usernames.update(self._normalize_list(data["usernames"]))
        if "emails" in data:
            identity.emails.update(self._normalize_list(data["emails"]))
        if "phones" in data:
            identity.phones.update(self._normalize_list(data["phones"]))
        if "profiles" in data:
            identity.profiles.update(data["profiles"])
        if "locations" in data:
            identity.locations.update(self._normalize_list(data["locations"]))
        if "organizations" in data:
            identity.organizations.update(self._normalize_list(data["organizations"]))
        if "interests" in data:
            identity.interests.update(self._normalize_list(data["interests"]))
        if "avatar_urls" in data:
            identity.avatar_urls.update(self._normalize_list(data["avatar_urls"]))

        # เพิ่ม source evidence
        identity.sources.append({
            "source": source,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "confidence": confidence,
        })

        # อัปเดต timestamps
        if not identity.first_seen:
            identity.first_seen = datetime.now()
        identity.last_updated = datetime.now()

        # คำนวณ confidence score ใหม่
        identity.confidence_score = self._calculate_confidence(identity)

        return identity

    def _find_or_create_identity(self, data: Dict) -> Identity:
        """หา identity ที่ตรงกัน หรือสร้างใหม่"""

        # สร้าง signature จาก data
        signature_keys = set()
        for key in ["usernames", "emails", "phones"]:
            if key in data:
                signature_keys.update(self._normalize_list(data[key]))

        # หา identity ที่มี overlap
        for identity in self.identities:
            identity_keys = identity.usernames | identity.emails | identity.phones

            # ถ้ามี overlap > 0 = เป็น identity เดียวกัน
            if signature_keys & identity_keys:
                return identity

        # ไม่เจอ = สร้างใหม่
        new_identity = Identity()
        self.identities.append(new_identity)
        return new_identity

    def _calculate_confidence(self, identity: Identity) -> float:
        """
        คำนวณ confidence score จาก:
        - จำนวน sources (มากกว่า 1 = ดีกว่า)
        - จำนวน identifiers (email, phone, username)
        - จำนวน profiles
        - confidence ของแต่ละ source
        """
        score = 0.0

        # จำนวน sources
        num_sources = len(identity.sources)
        if num_sources >= 3:
            score += 0.3
        elif num_sources == 2:
            score += 0.2
        elif num_sources == 1:
            score += 0.1

        # จำนวน identifiers
        num_identifiers = len(identity.usernames) + len(identity.emails) + len(identity.phones)
        if num_identifiers >= 5:
            score += 0.3
        elif num_identifiers >= 3:
            score += 0.2
        elif num_identifiers >= 1:
            score += 0.1

        # จำนวน profiles
        num_profiles = len(identity.profiles)
        if num_profiles >= 5:
            score += 0.2
        elif num_profiles >= 3:
            score += 0.15
        elif num_profiles >= 1:
            score += 0.1

        # average confidence จาก sources
        if identity.sources:
            avg_confidence = sum(s["confidence"] for s in identity.sources) / len(identity.sources)
            score += avg_confidence * 0.2

        return min(score, 1.0)

    def _normalize_list(self, items) -> Set[str]:
        """แปลง list/set ให้เป็น set ของ string ที่ clean แล้ว"""
        if isinstance(items, str):
            return {items.strip().lower()}
        return {str(item).strip().lower() for item in items if item}

    def get_primary_identity(self) -> Optional[Identity]:
        """ดึง identity ที่มี confidence สูงสุด"""
        if not self.identities:
            return None
        return max(self.identities, key=lambda i: i.confidence_score)

    def get_all_identities(self) -> List[Identity]:
        """ดึง identities ทั้งหมด เรียงตาม confidence"""
        return sorted(self.identities, key=lambda i: i.confidence_score, reverse=True)

    def get_pivot_points(self) -> List[str]:
        """
        ดึง pivot points — identifiers ที่ควรสืบค้นต่อ
        เรียงตามความน่าสนใจ (emails, phones, usernames)
        """
        pivots = []

        for identity in self.identities:
            # Emails (มักมีข้อมูลเยอะ)
            pivots.extend(identity.emails)

            # Phones (สำคัญมาก)
            pivots.extend(identity.phones)

            # Usernames (ค้นหาได้ง่าย)
            pivots.extend(identity.usernames)

        # ลบ duplicate และเรียงลำดับ
        return list(dict.fromkeys(pivots))

    def format_report(self) -> str:
        """สร้างรายงานสรุป identities"""
        output = "# Identity Triangulation Report\n\n"

        if not self.identities:
            output += "ไม่พบ identity ใดๆ\n"
            return output

        for i, identity in enumerate(self.get_all_identities(), 1):
            output += f"## Identity #{i} (Confidence: {identity.confidence_score:.2f})\n\n"

            if identity.names:
                output += f"**Names**: {', '.join(identity.names)}\n\n"

            if identity.usernames:
                output += f"**Usernames**: {', '.join(identity.usernames)}\n\n"

            if identity.emails:
                output += f"**Emails**: {', '.join(identity.emails)}\n\n"

            if identity.phones:
                output += f"**Phones**: {', '.join(identity.phones)}\n\n"

            if identity.profiles:
                output += "**Profiles**:\n"
                for platform, url in identity.profiles.items():
                    output += f"  - {platform}: {url}\n"
                output += "\n"

            if identity.locations:
                output += f"**Locations**: {', '.join(identity.locations)}\n\n"

            if identity.organizations:
                output += f"**Organizations**: {', '.join(identity.organizations)}\n\n"

            output += f"**Sources**: {len(identity.sources)} sources\n\n"
            output += "---\n\n"

        return output
