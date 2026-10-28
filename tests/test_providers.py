import json

import httpx
import pytest

from osint_agent import agent, graph, providers


@pytest.mark.parametrize("url,protocol,expected", [
    ("https://api.maxplus-ai.cc/v1", "openai", "https://api.maxplus-ai.cc/v1"),
    ("https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1/models", "openai",
     "https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1"),
    ("https://api.maxplus-ai.cc/v1", "anthropic", "https://api.maxplus-ai.cc"),
])
def test_base_url_preserves_pool_and_normalizes_sdk_path(url, protocol, expected):
    assert providers.normalize_base_url(url, protocol) == expected


def test_openai_tool_loop_report_graph_and_model_listing(monkeypatch):
    requests = []
    outcomes = iter([
        {"content": None, "tool_calls": [{"id": "call-1", "type": "function", "function": {
            "name": "extract_entities", "arguments": '{"text":"test@example.com"}',
        }}]},
        {"content": "Collected fixture evidence"},
        {"content": "## Fixture report"},
        {"content": '{"nodes":[{"id":"target","label":"Fixture","group":"identifier"}],"edges":[]}'},
    ])

    def respond(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer ccsk-fixture"
        if request.method == "GET":
            assert request.url.path == "/gpt-pro-ultimate-lite/v1/models"
            return httpx.Response(200, json={"data": [{"id": "gpt-fixture"}]})
        assert request.url.path == "/gpt-pro-ultimate-lite/v1/chat/completions"
        message = next(outcomes)
        return httpx.Response(200, json={"choices": [{"message": message,
            "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}]})

    real_client = httpx.Client
    monkeypatch.setattr(providers.httpx, "Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond),
    ))
    keys = {"provider": "openai", "base_url": "https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1/models",
            "model": "gpt-fixture", "anthropic": "ccsk-fixture"}
    assert agent.list_provider_models(keys) == ["gpt-fixture"]
    events = []
    assert agent.run_osint_lookup("อีเมล", "test@example.com", "fixture", events.append, keys) == "## Fixture report"
    client = agent._build_client(**agent._client_overrides(keys))
    try:
        assert graph.build_relationship_graph(client, "## Fixture report", model="gpt-fixture")["nodes"][0]["id"] == "target"
    finally:
        client.close()
    payloads = [json.loads(request.content) for request in requests if request.method == "POST"]
    assert all(payload["model"] == "gpt-fixture" for payload in payloads)
    assert all(tool["type"] == "function" for tool in payloads[0]["tools"])
    assert any(tool["function"]["name"] == "google_search" for tool in payloads[0]["tools"])
    followup = payloads[1]["messages"]
    assert any(message.get("tool_calls", [{}])[0].get("id") == "call-1" for message in followup)
    assert any(message.get("tool_call_id") == "call-1" and "test@example.com" in message["content"] for message in followup)
    assert events[-1]["kind"] == "done"


def test_parallel_tool_results_precede_images():
    messages = [{"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "one", "content": [
            {"type": "text", "text": "image evidence"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "fixture"}},
        ]},
        {"type": "tool_result", "tool_use_id": "two", "content": [{"type": "text", "text": "other evidence"}]},
    ]}]
    converted = providers._chat_messages("", messages)
    assert [message["role"] for message in converted] == ["tool", "tool", "user"]
    assert converted[-1]["content"][1]["image_url"]["url"] == "data:image/png;base64,fixture"


def test_auth_failure_is_actionable_and_does_not_echo_provider_body(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(providers.httpx, "Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(
            401, json={"error": "invalid token secret-fixture"},
        )),
    ))
    client = providers.OpenAICompatibleClient("ccsk-fixture", "https://api.maxplus-ai.cc/v1")
    try:
        with pytest.raises(providers.ProviderAPIError, match="Base URL") as error:
            client.list_models()
        assert error.value.status_code == 401
        assert "secret-fixture" not in str(error.value)
    finally:
        client.close()
