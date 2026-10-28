from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from osint_agent import access, agent, graph, report_export

APP = Path(__file__).resolve().parents[1] / "app_modern.py"


@pytest.fixture
def app_dependencies(monkeypatch):
    def lookup(**kwargs):
        kwargs["on_event"]({"kind": "tool", "text": "fetch_page fixture"})
        kwargs["on_event"]({"kind": "result", "text": "fixture evidence"})
        kwargs["on_event"]({"kind": "done", "text": "complete"})
        return f"## Fixture report\n\nTarget: {kwargs['identifier_value']}"

    lookup_mock = Mock(side_effect=lookup)
    client_builder = Mock(return_value=Mock())
    graph_builder = Mock(return_value={
        "nodes": [{"id": "target", "label": "Target", "group": "identifier"},
                  {"id": "source", "label": "Source", "group": "source"}],
        "edges": [],
    })
    exporter = Mock(wraps=report_export.build_report_html)
    monkeypatch.setattr(agent, "run_osint_lookup", lookup_mock)
    monkeypatch.setattr(agent, "_build_client", client_builder)
    monkeypatch.setattr(graph, "build_relationship_graph", graph_builder)
    monkeypatch.setattr(graph, "build_graph_html", Mock(return_value="<html>Fixture graph</html>"))
    monkeypatch.setattr(report_export, "build_report_html", exporter)
    monkeypatch.setattr(access, "audit", Mock())
    return lookup_mock, client_builder, graph_builder, exporter


def investigate(app, value="review-user"):
    app.text_input[-1].set_value(value)
    app.button(key="FormSubmitter:investigate-เริ่มสืบสวน  →").click().run()
    assert not app.exception


def test_report_graph_and_downloads_survive_rerun(app_dependencies):
    lookup, client_builder, graph_builder, exporter = app_dependencies
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.session_state["saved_anthropic_key"] = "review-fixture-key"
    investigate(app)
    assert not app.error
    assert len(app.tabs) == 3
    assert len(app.get("download_button")) == 2
    client_builder.assert_called_once_with(api_key_override="review-fixture-key")
    client_builder.return_value.close.assert_called_once()
    assert exporter.call_args.kwargs["identifier_value"] == "review-user"
    assert "Fixture report" in exporter.call_args.kwargs["report_md"]
    assert exporter.call_args.kwargs["stats"]["tool"] == 1
    generated_at = exporter.call_args.kwargs["generated_at"]

    app.run()
    assert not app.exception and not app.error
    assert len(app.tabs) == 3
    assert len(app.get("download_button")) == 2
    lookup.assert_called_once()
    graph_builder.assert_called_once()
    assert exporter.call_args.kwargs["generated_at"] == generated_at


@pytest.mark.parametrize("failure_at", ["client", "graph"])
def test_graph_failure_keeps_report_and_both_downloads(app_dependencies, failure_at):
    _, client_builder, graph_builder, _ = app_dependencies
    failed = client_builder if failure_at == "client" else graph_builder
    failed.side_effect = RuntimeError("fixture graph unavailable")
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    investigate(app)
    assert not app.error
    assert len(app.get("download_button")) == 2
    assert any("ผังความสัมพันธ์ไม่สำเร็จ" in item.value for item in app.warning)


def test_new_investigation_replaces_previous_result(app_dependencies):
    lookup, _, _, exporter = app_dependencies
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    investigate(app, "first-user")
    investigate(app, "second-user")
    assert lookup.call_count == 2
    assert exporter.call_args.kwargs["identifier_value"] == "second-user"
    assert "first-user" not in exporter.call_args.kwargs["report_md"]
    assert len(app.session_state["history"]) == 2


def test_lookup_failure_does_not_generate_graph_and_can_retry(app_dependencies):
    lookup, _, graph_builder, _ = app_dependencies
    lookup.side_effect = RuntimeError("fixture lookup unavailable")
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    investigate(app)
    assert any("fixture lookup unavailable" in item.value for item in app.error)
    graph_builder.assert_not_called()
    lookup.side_effect = None
    lookup.return_value = "## Recovered report"
    investigate(app, "retry-user")
    assert not app.error
    assert len(app.get("download_button")) == 2


@pytest.mark.parametrize("save_settings", [False, True])
def test_maxplus_settings_reach_both_investigation_and_graph(app_dependencies, monkeypatch, save_settings):
    lookup, client_builder, graph_builder, _ = app_dependencies
    models = Mock(return_value=["gpt-fixture"])
    monkeypatch.setattr(agent, "list_provider_models", models)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.selectbox(key="api_provider").select("MaxPlus GPT").run()
    app.text_input(key="anthropic_api_key").set_value("ccsk-fixture")
    app.button(key="load_provider_models").click().run()
    assert models.call_args.args[0]["base_url"] == "https://api.maxplus-ai.cc/v1"
    assert models.call_args.args[0]["provider"] == "openai"
    if save_settings:
        next(button for button in app.button if "บันทึก API Keys" in button.label).click().run()
    investigate(app)
    assert not app.error
    assert lookup.call_args.kwargs["api_keys"] == {
        "anthropic": "ccsk-fixture", "provider": "openai",
        "base_url": "https://api.maxplus-ai.cc/v1", "model": "gpt-fixture",
    }
    client_builder.assert_called_once_with(
        api_key_override="ccsk-fixture", provider_override="openai",
        base_url_override="https://api.maxplus-ai.cc/v1",
    )
    assert graph_builder.call_args.kwargs["model"] == "gpt-fixture"


def test_current_settings_replace_previously_saved_settings(app_dependencies):
    lookup, client_builder, graph_builder, _ = app_dependencies
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.selectbox(key="api_provider").select("MaxPlus Claude").run()
    app.text_input(key="anthropic_api_key").set_value("ccsk-old-fixture")
    next(button for button in app.button if "บันทึก API Keys" in button.label).click().run()

    app.selectbox(key="api_provider").select("MaxPlus GPT").run()
    app.text_input(key="anthropic_api_key").set_value("ccsk-new-fixture")
    app.text_input(key="api_base_url_MaxPlus GPT").set_value("https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1")
    app.text_input(key="api_model_MaxPlus GPT").set_value("gpt-fixture")
    investigate(app)

    assert not app.error
    assert lookup.call_args.kwargs["api_keys"] == {
        "anthropic": "ccsk-new-fixture", "provider": "openai",
        "base_url": "https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1", "model": "gpt-fixture",
    }
    client_builder.assert_called_once_with(
        api_key_override="ccsk-new-fixture", provider_override="openai",
        base_url_override="https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1",
    )
    assert graph_builder.call_args.kwargs["model"] == "gpt-fixture"
