"""ค้นหาแบบ multi-engine ผ่าน Moli พร้อม fallback ddgs → googlesearch

ทุก engine ถูกจำแนกสถานะ ok/empty/blocked/failed แยกกัน และ dedupe URL ก่อนคืน
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from . import browser

MAX_ENGINES = 4
PER_ENGINE_LIMIT = 10
DEFAULT_ENGINES = "duckduckgo_html,yahoo_uk,brave"


@dataclass(frozen=True)
class Engine:
    key: str
    label: str
    url: str
    item_selector: str
    title_selector: str
    snippet_selector: str


ENGINES = {
    "duckduckgo_html": Engine(
        "duckduckgo_html", "DuckDuckGo HTML", "https://html.duckduckgo.com/html/?q={q}",
        "div.result", ".result__a", ".result__snippet",
    ),
    "duckduckgo_lite": Engine(
        "duckduckgo_lite", "DuckDuckGo Lite", "https://lite.duckduckgo.com/lite/?q={q}",
        "tr", "a.result-link", "td.result-snippet",
    ),
    "yahoo_uk": Engine(
        "yahoo_uk", "Yahoo UK", "https://uk.search.yahoo.com/search?p={q}",
        "div.algo", "h3 a", ".compText",
    ),
    "yahoo_tw": Engine(
        "yahoo_tw", "Yahoo TW", "https://tw.search.yahoo.com/search?p={q}",
        "div.algo", "h3 a", ".compText",
    ),
    "brave": Engine(
        "brave", "Brave", "https://search.brave.com/search?q={q}",
        "div.snippet", "a", ".snippet-description",
    ),
    "bing": Engine(
        "bing", "Bing", "https://www.bing.com/search?q={q}",
        "li.b_algo", "h2 a", ".b_caption p",
    ),
    "yandex": Engine(
        "yandex", "Yandex", "https://yandex.com/search/?text={q}",
        "li.serp-item", "a.organic__url, a", ".organic__url-text, .text-container",
    ),
}


@dataclass
class EngineOutcome:
    engine: str
    status: str
    results: list[dict] = field(default_factory=list)
    detail: str = ""


def enabled_engines() -> list[Engine]:
    raw = os.environ.get("OSINT_SEARCH_ENGINES", DEFAULT_ENGINES)
    keys = [part.strip() for part in raw.split(",") if part.strip()]
    return [ENGINES[key] for key in keys[:MAX_ENGINES] if key in ENGINES]


def _expression(engine: Engine) -> str:
    item = json.dumps(engine.item_selector)
    title = json.dumps(engine.title_selector)
    snippet = json.dumps(engine.snippet_selector)
    return (
        "(() => Array.from(document.querySelectorAll(" + item + ")).slice(0, 10).map(el => ({"
        "title: ((el.querySelector(" + title + ")||{}).innerText||'').trim(),"
        "url: ((el.querySelector('a')||{}).href||''),"
        "snippet: ((el.querySelector(" + snippet + ")||{}).innerText||'').trim()"
        "})).filter(r => r.url && r.title))()"
    )


def _extract(engine: Engine, query: str) -> EngineOutcome:
    url = engine.url.format(q=quote_plus(query))
    try:
        raw = browser.fetch_eval(url, _expression(engine), timeout=25).strip()
    except browser.BrowserError as exc:
        message = str(exc)
        status = "blocked" if any(k in message for k in ("429", "403", "challenge", "blocked")) else "failed"
        return EngineOutcome(engine.key, status, detail=message[:160])

    try:
        payload = json.loads(raw) if raw else []
    except ValueError:
        return EngineOutcome(engine.key, "failed", detail="อ่านผลไม่ได้")
    if not isinstance(payload, list):
        return EngineOutcome(engine.key, "failed", detail="รูปแบบผลไม่ใช่ array")
    if not payload:
        return EngineOutcome(engine.key, "empty", detail="ไม่พบผล")

    results = []
    for item in payload[:PER_ENGINE_LIMIT]:
        if not isinstance(item, dict):
            continue
        url_value = str(item.get("url") or "").strip()
        if not url_value.startswith("http"):
            continue
        results.append(
            {
                "engine": engine.key,
                "label": engine.label,
                "title": str(item.get("title") or "").strip()[:200],
                "url": url_value,
                "snippet": str(item.get("snippet") or "").strip()[:300],
            }
        )
    return EngineOutcome(engine.key, "ok" if results else "empty", results)


def _dedupe(results: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for item in results:
        # ตัด query string ที่ไม่จำเป็นเพื่อกันผลซ้ำจาก tracking
        key = item["url"].split("#", 1)[0].split("?", 1)[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _ddgs(query: str, limit: int) -> list[dict]:
    from ddgs import DDGS

    rows = DDGS().text(query, max_results=limit)
    return [
        {
            "engine": "ddgs",
            "label": "DDGS metasearch",
            "title": str(row.get("title") or ""),
            "url": str(row.get("href") or row.get("url") or ""),
            "snippet": str(row.get("body") or ""),
        }
        for row in rows
        if row.get("href") or row.get("url")
    ]


def _googlesearch(query: str, limit: int, lang: str, region: str) -> list[dict]:
    from googlesearch import search as google_search

    rows = google_search(
        query, num_results=limit, lang=lang, region=region, sleep_interval=1.2, advanced=True
    )
    return [
        {"engine": "googlesearch", "label": "Google scraping", "title": str(getattr(r, "title", "")), "url": str(getattr(r, "url", r)), "snippet": str(getattr(r, "description", ""))}
        for r in rows
    ]


def search(
    query: str, limit: int = 10, lang: str = "th", region: str = "th"
) -> dict:
    limit = max(1, min(limit, 30))
    engines = enabled_engines()
    outcomes: list[EngineOutcome] = []

    if engines and browser.available():
        with ThreadPoolExecutor(max_workers=min(3, len(engines))) as pool:
            futures = [pool.submit(_extract, engine, query) for engine in engines]
            for future in as_completed(futures):
                outcomes.append(future.result())

    results = _dedupe([item for outcome in outcomes for item in outcome.results])[:limit]

    if not results:
        try:
            fallback = _ddgs(query, limit)
            if fallback:
                outcomes.append(EngineOutcome("ddgs", "ok", _dedupe(fallback)[:limit]))
                results = _dedupe(fallback)[:limit]
        except Exception as exc:  # noqa: BLE001
            outcomes.append(EngineOutcome("ddgs", "failed", detail=type(exc).__name__))
        if not results:
            try:
                fallback = _googlesearch(query, limit, lang, region)
                if fallback:
                    outcomes.append(EngineOutcome("googlesearch", "ok", fallback[:limit]))
                    results = fallback[:limit]
            except Exception as exc:  # noqa: BLE001
                outcomes.append(EngineOutcome("googlesearch", "failed", detail=type(exc).__name__))

    return {
        "query": query,
        "results": results,
        "engines": [
            {"engine": o.engine, "status": o.status, "count": len(o.results), "detail": o.detail}
            for o in outcomes
        ],
    }
