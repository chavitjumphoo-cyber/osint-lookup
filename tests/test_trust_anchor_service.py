
from osint_agent.services import trust_anchor as service
from vendor.osint_d2.core.domain.models import SocialProfile


class FakeScanner:
    def __init__(self, settings=None):
        pass

    async def scan(self, username):
        if username == "janellerivera":
            return SocialProfile(
                url="https://github.com/janellerivera",
                username=username,
                network_name="github",
                exists=True,
                metadata={"name": "Janelle Rivera"},
                bio="python security",
            )
        return SocialProfile(
            url=f"https://github.com/{username}",
            username=username,
            network_name="github",
            exists=True,
            metadata={"name": "Janelle Castro"},
        )


def test_apply_trust_drops_namesake(monkeypatch):
    monkeypatch.setattr(service, "SCANNER_CLASSES", {"github": FakeScanner})
    result = service.apply_trust("janellerivera", ["github:janellerivera"])
    assert result.reference_names
    assert all("rivera" in profile.username for profile in result.kept)


def test_apply_trust_without_anchors():
    assert service.apply_trust("johndoe", []).kept == []


def test_invalid_anchor_is_ignored(monkeypatch):
    monkeypatch.setattr(service, "SCANNER_CLASSES", {"github": FakeScanner})
    result = service.apply_trust("johndoe", ["broken-anchor"])
    assert result.errors


def test_anchor_evidence_text():
    assert "github:x" in service.anchors_evidence(["github:x"])
