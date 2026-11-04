from vendor._compat import settings_from_project
from vendor.osint_d2.core.domain.models import SocialProfile
from vendor.osint_d2.services import trust_anchor as ta
from vendor.osint_d2.services.url_guard import SSRFBlockedError, validate_url
from vendor.synint.core.context import InvestigationContext
from vendor.synint.core.identity_resolution import IdentityResolver
from vendor.synint.core.registries import EntityRegistry, EvidenceRegistry
from vendor.synint.core.schemas import Entity, EvidenceItem
from vendor.synint.core.validation import validate_result


def _evidence(source="github", value="a@b.com"):
    return EvidenceItem(
        source_agent=source,
        evidence_type="email",
        value=value,
        normalized_value=value.lower(),
        confidence=0.7,
    )


def test_evidence_registry_dedupes_identical_items():
    registry = EvidenceRegistry()
    first = registry.add(_evidence())
    registry.add(_evidence())
    assert len(registry) == 1
    assert registry.get(first) is not None


def test_evidence_registry_merges_same_item_with_higher_confidence():
    registry = EvidenceRegistry()
    registry.add(_evidence())
    stronger = _evidence()
    stronger.confidence = 0.95
    registry.add(stronger)
    items = registry.items()
    assert len(items) == 1
    assert items[0].confidence == 0.95


def test_entity_registry_merges_on_same_id():
    registry = EntityRegistry()
    registry.add(Entity(entity_type="email", canonical_name="a@b.com"))
    registry.add(Entity(entity_type="email", canonical_name="a@b.com", confidence=0.9))
    entity_id = registry.to_list()[0]["entity_id"]
    assert registry.get(entity_id).confidence == 0.9


def test_context_infers_phone_type():
    context = InvestigationContext.from_target("+66812345678")
    assert context.target_type == "phone"
    assert context.normalized_target == "+66812345678"


def test_identity_resolver_finds_exact_email_candidate():
    candidates = IdentityResolver.create_candidates(
        [
            {"entity_id": "e1", "emails": ["a@b.com"]},
            {"entity_id": "e2", "emails": ["A@B.com"]},
        ]
    )
    assert len(candidates) == 1
    assert candidates[0].status == "CANDIDATE"
    assert any(signal.signal_type == "EXACT_NORMALIZED_EMAIL" for signal in candidates[0].supporting_signals)


def test_identity_resolver_keeps_strangers_apart():
    candidates = IdentityResolver.create_candidates(
        [
            {"entity_id": "e1", "emails": ["a@b.com"]},
            {"entity_id": "e2", "emails": ["c@d.com"]},
        ]
    )
    assert candidates == []


def test_trust_anchor_verifies_trusted_profile():
    anchor = ta.TrustAnchor.parse("github:jdoe88")
    profile = SocialProfile(
        url="https://github.com/jdoe88",
        username="jdoe88",
        network_name="github",
        exists=True,
        metadata={"name": "John Doe", "location": "Bangkok"},
        bio="python security researcher",
    )
    reference = ta.build_reference_from_profiles([profile], [anchor])
    result = ta.verify_profile(profile, reference)
    assert result.verified is True
    assert result.confidence == 1.0


def test_trust_anchor_rejects_name_contradiction():
    anchor = ta.TrustAnchor.parse("github:janellerivera")
    trusted = SocialProfile(
        url="https://github.com/janellerivera",
        username="janellerivera",
        network_name="github",
        exists=True,
        metadata={"name": "Janelle Rivera"},
    )
    reference = ta.build_reference_from_profiles([trusted], [anchor])

    namesake = SocialProfile(
        url="https://pinterest.com/janellerivera",
        username="janellerivera",
        network_name="pinterest",
        exists=True,
        metadata={"name": "Janelle Castro"},
    )
    result = ta.verify_profile(namesake, reference)
    assert result.verified is False


def test_url_guard_blocks_loopback():
    assert validate_url("https://github.com").startswith("https://")
    try:
        validate_url("http://127.0.0.1:8501")
    except SSRFBlockedError:
        pass
    else:
        raise AssertionError("loopback must be blocked")


def test_validate_result_accepts_and_rejects():
    ok, cleaned, error = validate_result(
        {"status": "ok", "agent": "x", "findings": {}, "risk_score": 2}
    )
    assert ok and error is None and cleaned["risk_score"] == 1.0

    ok, _, error = validate_result({"status": "weird", "agent": "x", "findings": {}})
    assert not ok and "invalid status" in error


def test_compat_settings_use_project_env(monkeypatch):
    monkeypatch.setattr(
        "osint_agent.agent.read_config",
        lambda: {
            "ANTHROPIC_API_KEY": "sk-test",
            "ANTHROPIC_BASE_URL": "https://api.example.test",
            "ANTHROPIC_MODEL": "claude-test",
            "HIBP_API_KEY": "hibp-test",
        },
    )
    settings = settings_from_project()
    assert settings.ai_model == "claude-test"
    assert settings.ai_base_url == "https://api.example.test"
    assert settings.hibp_api_key.get_secret_value() == "hibp-test"


def test_every_vendored_module_imports():
    import importlib
    import pathlib

    failures = []
    for path in pathlib.Path("vendor").rglob("*.py"):
        if path.name == "__init__.py":
            continue
        module = ".".join(path.with_suffix("").parts)
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{module}: {type(exc).__name__}: {exc}")
    assert not failures, "\n".join(failures)
