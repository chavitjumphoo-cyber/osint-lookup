import json

from osint_agent.tools import intel


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_dns_lookup_parses_answers(monkeypatch):
    monkeypatch.setattr(
        intel,
        "safe_get",
        lambda url, **kw: FakeResponse(payload={"Answer": [{"data": "1.2.3.4"}]}),
    )
    out = intel.run_dns_lookup("example.com")["output"]
    assert "1.2.3.4" in out


def test_whois_reports_events(monkeypatch):
    monkeypatch.setattr(
        intel,
        "safe_get",
        lambda url, **kw: FakeResponse(
            payload={"events": [{"eventAction": "registration", "eventDate": "2020-01-01"}],
                     "entities": [{"roles": ["registrar"], "vcardArray": [[], [["fn", {}, "text", "Reg Inc"]]]}]}
        ),
    )
    out = intel.run_whois_lookup("example.com")["output"]
    assert "registration" in out and "Reg Inc" in out


def test_wayback_handles_empty(monkeypatch):
    monkeypatch.setattr(intel, "safe_get", lambda url, **kw: FakeResponse(payload=[["timestamp"]]))
    assert "ไม่พบ snapshot" in intel.run_wayback_lookup("example.com")["output"]


def test_github_intel_404(monkeypatch):
    monkeypatch.setattr(intel, "safe_get", lambda url, **kw: FakeResponse(status=404))
    assert "ไม่พบ" in intel.run_github_intel("nobody")["output"]


def test_gravatar_parses_entry(monkeypatch):
    monkeypatch.setattr(
        intel,
        "safe_get",
        lambda url, **kw: FakeResponse(payload={"entry": [{"displayName": "Jane", "accounts": [{"shortname": "gh", "url": "https://github.com/jane"}]}]}),
    )
    out = intel.run_gravatar_lookup("jane@example.com")["output"]
    assert "Jane" in out and "github.com/jane" in out


def test_tools_registered():
    from osint_agent.tools import TOOLS

    for name in ("dns_lookup", "whois_lookup", "wayback_lookup", "github_intel", "gravatar_lookup"):
        assert name in TOOLS


def test_json_dumps():
    assert json.loads(intel.json_dumps({"a": 1})) == {"a": 1}
