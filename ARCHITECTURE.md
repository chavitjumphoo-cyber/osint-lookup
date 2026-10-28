# Architecture

## Request flow

```text
Streamlit form (app_modern.py)
    -> run_osint_lookup(identifier_type, identifier_value, context, on_event, api_keys)
    -> shared ReAct loop (agent.py), with Anthropic or OpenAI-compatible transport
    -> build_tool_list() / execute_tool(name, input) (tools.py)
    -> public-source tools and local analysis
    -> Markdown report
    -> optional relationship graph
    -> HTML / Markdown downloads
```

The application remains Python/Streamlit. The existing module paths, tool names,
API-key configuration, and agent entry point are preserved.

## Module boundaries

- `agent.py` owns provider configuration, model calls, step limits, and callbacks.
  It accepts the existing Google settings for compatibility without placing a
  browser session's credentials into process-wide environment variables.
- `providers.py` maps the existing message/tool contract to OpenAI-compatible
  chat completions for MaxPlus GPT. It retains function calls, tool results,
  and image attachments. Hosted Anthropic search is omitted in this mode;
  the existing local DuckDuckGo tool remains available. Base URLs preserve pool
  paths and normalize pasted model-list URLs. Authentication errors do not echo
  the provider response body.
- `tools.py` owns the agent-facing tool schemas and dispatcher. Tool results retain
  the `{output: str, images: list}` contract. The `google_search` name is retained
  while its implementation uses DuckDuckGo.
- `network.py` owns shared public-host URL checks, redirect validation, per-domain
  throttling, and bounded image downloads. Existing imports such as
  `tools.safe_get`, `tools.UnsafeURLError`, and `tools.DomainRateLimiter` remain
  available as compatibility re-exports.
- `advanced_tools.py` owns phone scanning, image hashes, and text similarity.
  `PhoneScanResult.associated_names` remains the public result field. The duplicate
  unreachable phone-scanning implementation has been removed.
- `platform_scanner.py` owns platform checks and evidence classification. Requests
  are sequential, with the existing inter-platform delay and shared HTTP safeguards.
- `graph.py` extracts a relationship graph from a completed report and renders it
  with PyVis. Graph generation is optional and isolated from report availability.
- `report_export.py` converts Markdown into printable HTML, escapes metadata, and
  sanitizes report markup. It receives named metadata arguments from the UI.
- `access.py` retains the existing local audit format and hash-chain verification.

## Stable result contracts

### Agent

`run_osint_lookup(...)` returns a report string. Its optional `on_event` callback
receives dictionaries with `kind` and `text`, as before.

### Platform scanner

`scan_multi_platform(identifier, identifier_type)` retains a list of confirmed
matches by default. The optional `include_unknown=True` includes ambiguous checks.
`PlatformScanner.check()` returns `None` for explicit HTTP 404/410 responses,
otherwise a dictionary containing the existing platform, URL, found, and data
fields plus a `status` of `found` or `unknown`.

`scan_username_advanced()` retains `username`, `platforms_found`, `total_found`,
and `scan_time`, and adds `platforms_unknown` and `total_unknown`. HTTP 200 by
itself is not enough to mark a profile as found. Matching profile metadata is
required; redirects, login pages, blocks, and ambiguous pages remain unknown.

## UI session state

`st.session_state["investigation"]` stores the target, report, events, timestamp,
status, graph, graph HTML, and error messages. API keys stay in the existing
session settings and are not copied into result data or audit events.

A form submission starts a new investigation. Other widget reruns render the
saved result without repeating model calls. Graph creation uses the same API-key
override, base URL, protocol, and model as the investigation. The model-list
button validates authentication without running inference. Both client types
are closed after use. Client cleanup and graph failures are handled
separately so the report and both download buttons remain available.

The report timestamp is fixed for that investigation, including after reruns.
A new submission replaces the displayed result and appends the existing history
metadata.

## Static launcher

`server.py` serves only `/landing.html`, `/features.html`, `/tools.html`, and
`/about.html`, with `/` and `/index.html` mapped to the landing page. `/app` retains
its redirect to the Streamlit port. GET and HEAD use the same allowlist. Secrets,
source files, Git metadata, audit files, and directory listings are not public routes.

The child process uses the current Python interpreter and the project directory,
so launch behavior does not depend on the shell's working directory. Ctrl+C also
terminates the Streamlit child process.

## Verification

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pip check
```

The suite includes offline tool tests, an agent conversation fixture, Streamlit
AppTest flows, actual PyVis HTML rendering, and local HTTP routing checks. Network
and LLM fixtures do not establish compatibility with a live provider or prove that
third-party platform markup has remained unchanged.
