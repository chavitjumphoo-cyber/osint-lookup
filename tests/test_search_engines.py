import json

from osint_agent.services import search_engines as se


def _payload(prefix):
    return json.dumps(
        [{"title": f"{prefix} title", "url": f"https://{prefix}.test/a?utm=1", "snippet": "s"}]
    )


def test_enabled_engines_respects_env(monkeypatch):
    monkeypatch.setenv("OSINT_SEARCH_ENGINES", "brave,unknown,duckduckgo_html")
    keys = [engine.key for engine in se.enabled_engines()]
    assert keys == ["brave", "duckduckgo_html"]


def test_expression_contains_selectors():
    expr = se._expression(se.ENGINES["duckduckgo_html"])
    assert "result__a" in expr
    assert "querySelectorAll" in expr


def test_dedupe_strips_tracking(monkeypatch):
    rows = [
        {"url": "https://a.test/x?utm=1"},
        {"url": "https://a.test/x?utm=2"},
        {"url": "https://b.test/y"},
    ]
    assert len(se._dedupe(rows)) == 2


def test_extract_marks_empty(monkeypatch):
    monkeypatch.setattr(se.browser, "fetch_eval", lambda *a, **k: "[]")
    outcome = se._extract(se.ENGINES["brave"], "q")
    assert outcome.status == "empty"


def test_extract_marks_blocked_on_429(monkeypatch):
    def boom(*a, **k):
        raise se.browser.BrowserError("moli exit 1: HTTP 429")

    monkeypatch.setattr(se.browser, "fetch_eval", boom)
    outcome = se._extract(se.ENGINES["brave"], "q")
    assert outcome.status == "blocked"


def test_search_collects_and_dedupes(monkeypatch):
    monkeypatch.setenv("OSINT_SEARCH_ENGINES", "brave,yahoo_uk")
    monkeypatch.setattr(se.browser, "available", lambda: True)
    mapping = {
        "https://search.brave.com": _payload("a"),
        "https://uk.search.yahoo.com": _payload("a"),
    }
    monkeypatch.setattr(
        se.browser,
        "fetch_eval",
        lambda url, expr, timeout=0: next(v for k, v in mapping.items() if url.startswith(k)),
    )
    payload = se.search("q", limit=10)
    assert len(payload["results"]) == 1
    assert {e["status"] for e in payload["engines"]} == {"ok"}


def test_search_falls_back_to_ddgs(monkeypatch):
    monkeypatch.setenv("OSINT_SEARCH_ENGINES", "brave")
    monkeypatch.setattr(se.browser, "available", lambda: False)
    monkeypatch.setattr(
        se,
        "_ddgs",
        lambda q, n: [{"engine": "ddgs", "title": "t", "url": "https://d.test", "snippet": ""}],
    )
    payload = se.search("q")
    assert payload["results"][0]["engine"] == "ddgs"


def test_search_falls_back_to_googlesearch(monkeypatch):
    monkeypatch.setenv("OSINT_SEARCH_ENGINES", "brave")
    monkeypatch.setattr(se.browser, "available", lambda: False)
    monkeypatch.setattr(se, "_ddgs", lambda q, n: [])
    monkeypatch.setattr(
        se,
        "_googlesearch",
        lambda q, n, lang, region: [{"engine": "googlesearch", "title": "t", "url": "https://g.test", "snippet": ""}],
    )
    payload = se.search("q")
    assert payload["results"][0]["engine"] == "googlesearch"


def test_web_search_tool_formats(monkeypatch):
    from osint_agent.tools import execute_tool

    monkeypatch.setattr(
        se,
        "search",
        lambda *a, **k: {
            "query": "q",
            "results": [{"engine": "brave", "label": "Brave", "title": "T", "url": "https://x.test", "snippet": "s"}],
            "engines": [{"engine": "brave", "status": "ok", "count": 1, "detail": ""}],
        },
    )
    out = execute_tool("web_search", {"query": "q"})["output"]
    assert "https://x.test" in out
    assert "brave=ok" in out


def test_google_search_alias(monkeypatch):
    from osint_agent.tools import execute_tool

    monkeypatch.setattr(
        se, "search", lambda *a, **k: {"query": "q", "results": [], "engines": []}
    )
    assert "Web Search" in execute_tool("google_search", {"query": "q"})["output"]
