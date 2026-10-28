from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from osint_agent import agent


def test_maxplus_key_without_endpoint_is_not_sent_to_anthropic(monkeypatch):
    monkeypatch.setattr(agent, "read_config", lambda: {})
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="MaxPlus"):
        agent._build_client(api_key_override="ccsk-fixture-not-a-real-key")


def test_native_provider_settings_keep_config_and_override_precedence(monkeypatch):
    monkeypatch.setattr(agent, "read_config", lambda: {
        "ANTHROPIC_API_KEY": "config-fixture", "ANTHROPIC_BASE_URL": "https://config.example",
        "OSINT_MODEL": "config-model",
    })
    monkeypatch.setenv("ANTHROPIC_API_KEY", "environment-fixture")
    client = agent._build_client("override-fixture", base_url_override="https://api.maxplus-ai.cc/v1")
    try:
        assert client.api_key == "override-fixture"
        assert str(client.base_url) == "https://api.maxplus-ai.cc"
    finally:
        client.close()
    assert agent._configured_model() == "config-model"
    assert agent._configured_model({"model": "session-model"}) == "session-model"


def test_lookup_closes_client_after_api_failure(monkeypatch):
    client = Mock()
    client.messages.create.side_effect = RuntimeError("fixture API unavailable")
    monkeypatch.setattr(agent, "_build_client", Mock(return_value=client))
    with pytest.raises(RuntimeError, match="fixture API unavailable"):
        agent.run_osint_lookup("Username", "fixture", "")
    client.close.assert_called_once()


def test_original_tool_loop_and_report_contract_remain_compatible(monkeypatch):
    tool = SimpleNamespace(type="tool_use", id="fixture-tool", name="extract_entities",
                           input={"text": "contact test@example.com"})
    client = Mock()
    client.messages.create.side_effect = [
        SimpleNamespace(content=[tool], stop_reason="tool_use"),
        SimpleNamespace(content=[SimpleNamespace(type="text", text="Evidence collected")], stop_reason="end_turn"),
        SimpleNamespace(content=[SimpleNamespace(type="text", text="## Final report")]),
    ]
    builder = Mock(return_value=client)
    monkeypatch.setattr(agent, "_build_client", builder)
    monkeypatch.setenv("GOOGLE_API_KEY", "original-key")
    events = []
    report = agent.run_osint_lookup(
        "อีเมล", "test@example.com", "fixture context", on_event=events.append,
        api_keys={"anthropic": "fixture-key", "google": "session-key", "google_cx": "session-cx"},
    )
    assert report == "## Final report"
    builder.assert_called_once_with(api_key_override="fixture-key")
    client.close.assert_called_once()
    assert agent.os.environ["GOOGLE_API_KEY"] == "original-key"
    assert events[-1]["kind"] == "done"
    messages = client.messages.create.call_args.kwargs["messages"]
    results = [message for message in messages if isinstance(message["content"], list)
               and isinstance(message["content"][0], dict)]
    assert results[0]["content"][0]["tool_use_id"] == "fixture-tool"
    assert "test@example.com" in results[0]["content"][0]["content"][0]["text"]
