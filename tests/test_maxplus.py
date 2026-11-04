from osint_agent import agent
from vendor import _compat


def test_maxplus_config_builds_client(monkeypatch):
    monkeypatch.setattr(
        agent,
        "read_config",
        lambda: {
            "MAXPLUS_API_KEY": "mp-key",
            "MAXPLUS_BASE_URL": "https://api.maxplus.test",
            "MAXPLUS_MODEL": "mp-model",
        },
    )
    client = agent._build_client()
    assert client.api_key == "mp-key"
    assert "maxplus" in str(client.base_url)
    assert agent.model_name() == "mp-model"


def test_maxplus_overrides_anthropic(monkeypatch):
    monkeypatch.setattr(
        agent,
        "read_config",
        lambda: {
            "MAXPLUS_API_KEY": "mp",
            "MAXPLUS_BASE_URL": "https://mp.test",
            "ANTHROPIC_API_KEY": "ant",
            "ANTHROPIC_BASE_URL": "https://ant.test",
        },
    )
    client = agent._build_client()
    assert client.api_key == "mp"
    assert "mp.test" in str(client.base_url)


def test_anthropic_still_works(monkeypatch):
    monkeypatch.setattr(
        agent, "read_config", lambda: {"ANTHROPIC_API_KEY": "ant", "ANTHROPIC_MODEL": "claude-x"}
    )
    client = agent._build_client()
    assert client.api_key == "ant"
    assert agent.model_name() == "claude-x"


def test_compat_settings_use_maxplus(monkeypatch):
    monkeypatch.setattr(
        agent,
        "read_config",
        lambda: {
            "MAXPLUS_API_KEY": "mp",
            "MAXPLUS_BASE_URL": "https://mp.test",
            "MAXPLUS_MODEL": "mp-model",
        },
    )
    settings = _compat.settings_from_project()
    assert settings.ai_model == "mp-model"
    assert settings.ai_base_url == "https://mp.test"
