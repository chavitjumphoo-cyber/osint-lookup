"""Tests for SYNINT-inspired agents"""

import json
from osint_agent import synint_agents


def test_generate_username_variants():
    """ทดสอบการสร้าง username variants"""
    variants = synint_agents.generate_username_variants("john.doe")

    assert "johndoe" in variants
    assert "john_doe" in variants
    assert "john.doe" in variants
    assert len(variants) > 3


def test_username_correlation_basic():
    """ทดสอบ username correlation พื้นฐาน"""
    corpus = "ผู้ใช้ johndoe โพสต์ว่า... และ john_doe ได้กดไลก์"
    result = synint_agents.username_correlation_agent("john.doe", corpus)

    assert result["seed"] == "john.doe"
    assert len(result["generated_variants"]) > 0
    assert "johndoe" in result["matched_variants"]
    assert "john_doe" in result["matched_variants"]
    assert result["confidence_score"] > 0.3


def test_username_correlation_no_match():
    """ทดสอบกรณีไม่มี variant ตรงใน corpus"""
    corpus = "ไม่มีข้อความที่เกี่ยวข้อง"
    result = synint_agents.username_correlation_agent("testuser123", corpus)

    assert result["seed"] == "testuser123"
    assert len(result["matched_variants"]) == 0
    assert result["confidence_score"] < 0.2


def test_email_harvest_basic():
    """ทดสอบการสร้างรูปแบบอีเมล"""
    result = synint_agents.email_harvest_agent("example.com", "john", "doe")

    assert result["domain"] == "example.com"
    assert result["generated_count"] > 0
    assert "admin@example.com" in result["generated_addresses"]
    assert "info@example.com" in result["generated_addresses"]
    assert "john.doe@example.com" in result["generated_addresses"]
    assert result["email_hypothesis_only"] is True


def test_email_harvest_role_accounts():
    """ทดสอบว่ามี role accounts ครบ"""
    result = synint_agents.email_harvest_agent("test.com")

    generated = result["generated_addresses"]
    assert any("admin@" in addr for addr in generated)
    assert any("support@" in addr for addr in generated)
    assert any("security@" in addr for addr in generated)


def test_identity_candidate_no_entities():
    """ทดสอบกรณี entities น้อยเกินไป"""
    result = synint_agents.identity_candidate_agent([{"name": "John"}])

    assert result["candidate_count"] == 0
    assert "reason" in result


def test_identity_candidate_email_match():
    """ทดสอบการจับคู่ตาม email"""
    entities = [
        {"name": "John Doe", "email": "john@example.com"},
        {"name": "J. Doe", "email": "john@example.com"},
        {"name": "Jane Smith", "email": "jane@example.com"},
    ]
    result = synint_agents.identity_candidate_agent(entities)

    assert result["candidate_count"] >= 1
    email_matches = [c for c in result["identity_candidates"] if c["match_type"] == "email_match"]
    assert len(email_matches) >= 1
    assert email_matches[0]["signal"] == "john@example.com"
    assert email_matches[0]["confidence"] == "high"


def test_identity_candidate_username_match():
    """ทดสอบการจับคู่ตาม username"""
    entities = [
        {"name": "User A", "username": "johndoe"},
        {"name": "User B", "username": "johndoe"},
    ]
    result = synint_agents.identity_candidate_agent(entities)

    assert result["candidate_count"] >= 1
    username_matches = [c for c in result["identity_candidates"] if c["match_type"] == "username_match"]
    assert len(username_matches) >= 1
    assert username_matches[0]["confidence"] == "medium"


def test_darkweb_monitor_basic():
    """ทดสอบ darkweb monitor scaffold"""
    result = synint_agents.darkweb_monitor_agent("test@example.com")

    assert result["search_target"] == "test@example.com"
    assert "target_entropy" in result
    assert result["agent_classification"] == "enrichment_scaffold"
    assert "breach corpus" in result["local_sources_supported"]
    assert result["matching_hooks"]["email_match"] is True


def test_darkweb_monitor_entropy():
    """ทดสอบการคำนวณ entropy"""
    result1 = synint_agents.darkweb_monitor_agent("aaa")
    result2 = synint_agents.darkweb_monitor_agent("random123@test.com")

    # ข้อความที่ซับซ้อนกว่าควรได้ entropy สูงกว่า
    assert result2["target_entropy"] > result1["target_entropy"]


def test_person_profile_agent_empty():
    """ทดสอบกรณีไม่มี evidence"""
    result = synint_agents.person_profile_agent({})

    assert result["profile_summary"]["alias_count"] == 0
    assert result["profile_summary"]["email_count"] == 0
    assert result["confidence_score"] >= 0


def test_person_profile_agent_full():
    """ทดสอบกรณีมี evidence ครบ"""
    evidence = {
        "names": ["John Doe", "J. Doe"],
        "emails": ["john@example.com"],
        "phones": ["0812345678"],
        "usernames": ["johndoe"],
        "organizations": ["ACME Corp"],
        "locations": ["Bangkok"],
        "social_profiles": [
            {"platform": "twitter", "url": "https://twitter.com/johndoe"}
        ],
    }
    result = synint_agents.person_profile_agent(evidence)

    assert result["profile_summary"]["alias_count"] == 2
    assert result["profile_summary"]["email_count"] == 1
    assert result["profile_summary"]["phone_count"] == 1
    assert result["profile_summary"]["social_profile_count"] == 1
    assert result["confidence_score"] > 0.3
    assert len(result["direct_evidence"]) > 0


def test_shannon_entropy():
    """ทดสอบการคำนวณ Shannon entropy"""
    # ข้อความซ้ำๆ ควรได้ entropy ต่ำ
    low_entropy = synint_agents.shannon_entropy("aaaaaaa")

    # ข้อความหลากหลายควรได้ entropy สูง
    high_entropy = synint_agents.shannon_entropy("abcdefgh12345")

    assert high_entropy > low_entropy
    assert synint_agents.shannon_entropy("") == 0.0
