# OSINT Lookup

Streamlit application for public-source investigation using an Anthropic-compatible
ReAct agent. The existing phone, username, email, graph, and report workflows remain
available.

## Quick start

Use **Python 3.11 or newer**. The regression suite is tested on Python 3.13.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env to set your API key, or save a key in the application settings.
python -m streamlit run app_modern.py --server.address 127.0.0.1
```

The application opens at `http://localhost:8501`.

To use the existing landing pages and application launcher instead:

```bash
python server.py
```

This starts the landing page at `http://localhost:8000` and Streamlit at
`http://localhost:8506`. Press Ctrl+C to stop both processes.
The launcher serves only the four public HTML pages, including for HEAD requests.

## Configuration

An Anthropic-compatible or OpenAI-compatible API key is required for the investigation agent.
It can be saved through the UI, set in the project's `.env`, or provided as an
environment variable, in that order of precedence. Reports and graphs use the
same selected key and provider settings.

```env
ANTHROPIC_API_KEY=your-key
# Optional Anthropic-compatible provider:
# ANTHROPIC_BASE_URL=https://your-provider.example
# Optional protocol and model overrides (defaults: anthropic, claude-sonnet-5):
# OSINT_PROVIDER=anthropic
# OSINT_MODEL=claude-sonnet-5
# Optional Have I Been Pwned API key:
# HIBP_API_KEY=your-hibp-key
```

Copy `.env.example` as a starting point. Do not commit real credentials.
The default model identifier remains `claude-sonnet-5`; the configured provider
must support it. Existing Anthropic configuration remains valid.

### MaxPlus

In the API settings, choose **MaxPlus GPT** for a GPT pool or **MaxPlus Claude**
for a Claude pool, enter your `ccsk-…` key, then click **โหลดรายการโมเดล / ตรวจสอบ key**.
Select a model returned by your key and click **บันทึก API Keys** before starting
an investigation. Loading models checks authentication without generating a report.
Settings and keys are stored only in the current Streamlit session.

MaxPlus GPT uses `https://api.maxplus-ai.cc/v1` by default. A pool-specific URL
such as `https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1` is also accepted,
including a pasted `/v1/models` URL. The key must have access to that pool.
For configuration through `.env` instead of the UI:

```env
ANTHROPIC_API_KEY=your-maxplus-key
ANTHROPIC_BASE_URL=https://api.maxplus-ai.cc/v1
OSINT_PROVIDER=openai
OSINT_MODEL=your-model-id-from-the-model-list
```

MaxPlus Claude uses `OSINT_PROVIDER=anthropic`, base URL
`https://api.maxplus-ai.cc`, and a supported Claude model ID. A MaxPlus key
without an explicit base URL is rejected before contacting Anthropic.
OpenAI-compatible mode uses the same local tools, including DuckDuckGo search;
Anthropic's hosted `web_search` tool is available only in Anthropic mode.
See the [MaxPlus API documentation](https://maxplus-ai.cc/docs/api) for pool access.

The existing `google_search` tool name and saved Google settings remain accepted
for compatibility. Search currently uses DuckDuckGo through `ddgs`, without a
Google API key. Optional tools such as `sherlock_username` require their own
executable; the tool returns an explanation when it is unavailable.

## Features and result interpretation

- **Phone tools:** format validation, country/numbering metadata, public search,
  and footprint links. Number metadata and page probes are not proof of ownership
  or current service registration.
- **Username scanner:** checks the existing platform list. A profile is confirmed
  only when matching profile metadata is present. Login pages, access blocks,
  redirects, and ambiguous HTTP 200 responses are reported as **unknown**, rather
  than counted as accounts or treated as proof of absence.
- **Email tools:** entity extraction, possible-address generation, and optional
  breach metadata lookup. Generated addresses are hypotheses, not verified mailboxes.
- **Analysis:** avatar comparison, text similarity, and identity candidate tools.
  A matching username, avatar, or writing sample alone does not establish identity.
- **Reports:** Markdown display, HTML/Markdown downloads, and relationship graphs.
  Results, timeline events, and generated graphs persist across Streamlit reruns
  within the current browser session. A graph failure does not block downloads.

The agent's existing Python entry point remains:

```python
from osint_agent.agent import run_osint_lookup

report = run_osint_lookup(
    identifier_type="Username",
    identifier_value="example_user",
    context="Investigation context",
    on_event=lambda event: print(event),
    api_keys={"anthropic": "your-key"},
)
```

## Project layout

```text
app_modern.py               Streamlit UI and session state
server.py                   Landing-page server and Streamlit launcher
landing.html                Existing public landing page
features.html               Existing feature page
about.html                  Existing about page
tools.html                  Existing tools page
requirements.txt            Pinned runtime dependencies
requirements-dev.txt        Runtime dependencies plus pytest
.env.example                Configuration template without credentials
osint_agent/
    agent.py                ReAct loop and provider configuration
    providers.py            OpenAI-compatible message/tool transport
    tools.py                Existing tool schemas and dispatcher
    network.py              Shared URL checks, redirects, rate limiting, image limits
    platform_scanner.py     Profile checks with confirmed/unknown results
    advanced_tools.py       Phone, avatar, and text analysis
    phone_enhanced.py       Phone metadata and footprint links
    identity_triangulation.py  Identity correlation helpers
    synint_agents.py        Local correlation and enrichment helpers
    graph.py                Relationship extraction and PyVis rendering
    report_export.py        Sanitized, printable HTML reports
    access.py               Local audit logging
tests/                      Offline unit and UI regression tests
```

See `ARCHITECTURE.md` for module boundaries and compatibility details.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pip check
```

The default suite blocks unmocked Requests/httpx calls and uses fixtures for agent
and UI tests. It does not spend API credits or investigate real people. Tests
cover the original tool loop, valid/invalid phone numbers, URL restrictions and
redirects, profile uncertainty, report export, rerun persistence, API-key
propagation, graph failures, and public-file routing.

The root-level `test_simple.py`, `test_full.py`, and `test_osint.py` are legacy
manual integration scripts. Running them directly can make real requests and use
API credits; they are not part of the default pytest suite.

## Security and local data

Run investigations only with appropriate authorization and verify source evidence
before relying on a report. The app remains a local tool without user authentication.
Do not expose it publicly without adding authentication and appropriate network controls.

Agent-facing avatar URLs must be public HTTP(S) URLs; trusted Python callers can
still compare image bytes or local image files directly. Downloaded images have
size limits, and redirects are checked before following them. Generated HTML
reports remove executable markup from model output.

Audit events are written locally to `audit/audit.jsonl`. New audit files are
ignored by Git, and the landing server does not serve them. The repository already
contains a tracked audit file: ignore rules do not remove data from Git history.
Avoid committing investigation logs or credentials.
