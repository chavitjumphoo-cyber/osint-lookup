# Architecture Overview

## Frontend → Backend Flow

```
┌─────────────────────────────────────────────────────────┐
│         Streamlit UI (app_modern.py)                    │
│  - Input form (phone, email, username, etc.)            │
│  - API key settings (optional)                          │
│  - Real-time timeline & report display                  │
└──────────────────┬──────────────────────────────────────┘
                   │ run_osint_lookup()
                   ▼
┌─────────────────────────────────────────────────────────┐
│    ReAct Agent (osint_agent/agent.py)                   │
│  - Manages Claude conversation loop                     │
│  - Orchestrates tool selection                          │
│  - Coordinates with event callback                      │
└──────────────────┬──────────────────────────────────────┘
                   │ _build_tools() + tools.execute_tool()
                   ▼
┌─────────────────────────────────────────────────────────┐
│         Tool Execution Layer                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ tools.py — Core OSINT tools (15+)               │   │
│  │ - google_search, scan_phone, reverse_image      │   │
│  │ - email_lookup, domain_info, username_verify    │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ platform_scanner.py — Multi-platform search     │   │
│  │ - Facebook, Instagram, Twitter, GitHub, etc.    │   │
│  │ - 30+ platforms in parallel                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ advanced_tools.py — Analysis tools              │   │
│  │ - Avatar comparison (perceptual hash)           │   │
│  │ - Stylometry analysis (n-gram matching)         │   │
│  │ - WhatsApp status scanning                       │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ identity_triangulation.py — Correlation engine  │   │
│  │ - Links identities across platforms             │   │
│  │ - Builds social graph                           │   │
│  │ - Scores confidence of connections              │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────────┘
                   │ emit(event) callback
                   ▼
┌─────────────────────────────────────────────────────────┐
│    UI Update (Streamlit event callbacks)                │
│  - Timeline: Shows tool execution progress             │
│  - Report: Updates with findings in real-time          │
│  - Graph: Relationship visualization                   │
└─────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Frontend: `app_modern.py`

**Responsibilities:**
- Streamlit UI rendering
- Session state management (API keys, search history)
- Event-driven updates to timeline/report
- Report export (HTML/Markdown)

**Data Flow:**
```python
# User submits form
identifier_type, identifier_value → run_osint_lookup()
                                  ↓
                            on_event callback (real-time)
                                  ↓
                            Timeline + Report updates
```

### 2. Backend: `osint_agent/agent.py`

**ReAct Loop:**
```
1. Thought: Model thinks about what to do
2. Plan: Selects tools to execute
3. Execute: Runs selected tools via execute_tool()
4. Observe: Gets tool results
5. Reflect: Updates understanding
6. (repeat until done)
7. Synthesize: Generates final HTML report
```

**Key Functions:**
- `_build_client()` — Creates Anthropic client (supports MaxPlus)
- `_build_tools()` — Lists available tools for Claude
- `_run_tool_calls()` — Executes tools selected by Claude
- `_describe()` — Converts tool calls to UI events
- `run_osint_lookup()` — Main orchestration function

### 3. Tools Layer: `osint_agent/tools.py`

**Pattern:**
```python
def tool_name_schema():
    return {
        "name": "tool_name",
        "description": "What it does",
        "input_schema": {...}
    }

def execute_tool(name, input_params):
    return {
        "output": "Results as string",
        "images": [{"type": "image/...", "data": "base64..."}]
    }
```

**Tool Categories:**

| Category | Tools |
|----------|-------|
| Search | google_search, scan_phone, reverse_image |
| Lookup | email_lookup, domain_info, username_verify |
| Analysis | extract_email, analyze_text, correlate_accounts |
| Advanced | scan_avatars, compare_stylometry |

### 4. Platform Scanner: `platform_scanner.py`

**Parallel scanning across 30+ platforms:**

```python
# Runs async HTTP requests to multiple platforms
async for platform in [facebook, instagram, twitter, github, ...]:
    result = await check_username(username, platform)
    results[platform] = result
```

**Supported Platforms:**
- Social: Facebook, Instagram, Twitter, TikTok, LinkedIn, YouTube
- Developer: GitHub, GitLab, Stack Overflow, HackerRank
- Community: Pantip, Reddit, Medium, DeviantArt

### 5. Identity Triangulation: `identity_triangulation.py`

**Linking algorithm:**

```
1. Extract identifiers from each tool (emails, phones, usernames)
2. Build identity profile for each
3. Compare across platforms using:
   - Exact matches (username, email)
   - Fuzzy matches (similar names, birthdates)
   - Behavioral correlation (posting patterns, interests)
4. Score confidence (0-100)
5. Build graph of connections
```

## API Key Management

### Supported Providers

| Provider | Format | Usage |
|----------|--------|-------|
| Anthropic | sk-ant-... | Main Claude API |
| MaxPlus | ccsk-... | Claude-compatible (via ANTHROPIC_BASE_URL) |
| Google | AIzaSy... | Custom Search API |

### Priority Order

```python
# _build_client() uses this priority:
1. api_key_override (from frontend UI)
2. ANTHROPIC_API_KEY (from .env or environment)
3. Fall back if MaxPlus base_url is set
```

## Data Flow Example: Phone Search

```
Input: "0882594115"
  ↓
agent.py: run_osint_lookup(
  identifier_type="เบอร์โทรศัพท์",
  identifier_value="0882594115"
)
  ↓
tools.py: scan_phone_advanced("0882594115")
  │
  ├─→ phonenumbers.parse() — Format validation
  ├─→ HTTP requests to AIS/Dtac/True carrier APIs
  ├─→ Reverse lookup databases
  └─→ WhatsApp status check
  ↓
platform_scanner.py: scan_platforms("0882594115", identifier_type="phone")
  │
  ├─→ Convert to possible usernames/emails
  ├─→ Parallel search across 30+ platforms
  └─→ Aggregate results
  ↓
identity_triangulation.py: triangulate(all_results)
  │
  ├─→ Extract identities from each platform
  ├─→ Score confidence of connections
  └─→ Build relationship graph
  ↓
system_prompt.py: generate_report(findings)
  │
  └─→ Synthesize into HTML report with citations
```

## Event Callback System

**UI Real-time Updates:**

```python
# Frontend passes callback to agent
def on_event(event):
    if event['kind'] == 'search':
        timeline.add("🔍 Searching: " + event['text'])
    elif event['kind'] == 'tool':
        timeline.add("⚙️ Running: " + event['text'])
    elif event['kind'] == 'result':
        timeline.mark_done()
    elif event['kind'] == 'done':
        report.render(event['text'])

run_osint_lookup(..., on_event=on_event)
```

## Performance Considerations

1. **Parallel Execution**: Platform scanner uses asyncio for concurrent requests
2. **Rate Limiting**: Domain rate limiter prevents IP bans
3. **Caching**: Results cached per session
4. **Timeout Handling**: 15s fetch timeout, 180s max per tool
5. **Result Truncation**: Limits output to prevent token overflow

## Security & Compliance

- **Input Validation**: Regex patterns to prevent injection
- **API Key Handling**: Never logged, stored in session only
- **PDPA Compliance**: Agent prompted to consider privacy laws
- **Audit Logging**: access.py tracks all searches
- **Data Minimization**: Results limited to public data only

## Future Architecture Improvements

1. **Distributed Tools**: Run tool execution on separate workers
2. **Database**: Cache results for faster re-queries
3. **Webhooks**: Real-time notifications for tracking updates
4. **API Gateway**: RESTful API wrapper for headless usage
5. **Graph Database**: Neo4j for relationship queries
