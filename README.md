# OSINT Lookup — Intelligence-Grade Investigation Platform

AI-powered OSINT tool for comprehensive identity research across 30+ platforms using ReAct agent pattern.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env (see Configuration section)

# Run Streamlit app
python -m streamlit run app_modern.py
```

Then open browser: **http://localhost:8501**

## ⚙️ Configuration

### .env File

```env
# Required for Claude API
ANTHROPIC_API_KEY=sk-ant-... 
# OR use MaxPlus (API-compatible with Anthropic)
ANTHROPIC_API_KEY=ccsk-...
ANTHROPIC_BASE_URL=https://api.maxplus-ai.cc

# Optional — Google Search API
GOOGLE_API_KEY=AIzaSy...
GOOGLE_CX=your-search-engine-id
```

**API Keys are optional** — the app will use defaults from `.env` if not provided via UI.

## 📁 Project Structure

```
osint-lookup/
├── app_modern.py              # Streamlit UI (main app)
├── landing.html               # Landing page
├── .env                        # Configuration
├── requirements.txt            # Dependencies
└── osint_agent/                # Backend engine
    ├── agent.py               # ReAct loop orchestrator
    ├── tools.py               # 15+ OSINT tools
    ├── platform_scanner.py    # 30+ platform scanner
    ├── identity_triangulation.py  # Identity linking engine
    ├── advanced_tools.py      # Avatar/stylometry analysis
    ├── system_prompt.py       # AI agent instructions
    ├── synint_agents.py       # SYNINT-inspired agents
    ├── graph.py               # Relationship graph builder
    ├── report_export.py       # Report formatting
    └── access.py              # Audit logging
```

## 🔧 Features

### Core Tools
- **Phone Scanner**: WhatsApp status, SIM carrier lookup, international format detection
- **Email Lookup**: Gmail validation, domain analysis
- **Username Search**: Cross-platform verification
- **Reverse Image Search**: Avatar/photo lookup
- **Domain/URL Analysis**: WHOIS, DNS, registrar info

### Multi-Platform Scanner (30+)
- Social: Facebook, Instagram, Twitter/X, TikTok, LinkedIn, YouTube, Snapchat, Telegram
- Developer: GitHub, GitLab, Stack Overflow, HackerRank, LeetCode, Kaggle
- Forums: Pantip, Medium, Reddit, DeviantArt, Behance
- Gaming: Twitch, Steam, Xbox, PlayStation

### Advanced Analysis
- **Identity Triangulation**: Link identities across platforms
- **Avatar Comparison**: Perceptual hash matching
- **Stylometry Analysis**: Writing style correlation
- **Social Graph**: Relationship visualization

## 🧠 How It Works

1. **User Input**: Enter identifier (phone, email, username, etc.)
2. **ReAct Agent Loop**:
   - Thinks: What tools are needed?
   - Plans: Which platforms to search?
   - Acts: Gathers data from multiple sources
   - Observes: Analyzes results
   - Synthesizes: Correlates findings
3. **Report Generation**: HTML/Markdown export with evidence trail

## 🛠️ Tech Stack

- **Frontend**: Streamlit (Python-based, no Node.js required)
- **Backend**: Python 3.8+
- **AI**: Anthropic Claude (or MaxPlus-compatible API)
- **Search**: Google Custom Search + platform-specific APIs
- **Visualization**: PyVis (relationship graphs)

## 📋 Usage Example

```
Input: 0882594115 (Thai phone number)
Output:
  ├── Carrier: AIS (Thailand)
  ├── Associated Accounts:
  │   ├── Instagram: @username
  │   ├── Facebook: Profile URL
  │   └── GitHub: username
  ├── Connections:
  │   ├── Co-workers/Friends
  │   └── Related email addresses
  └── Confidence scores for each finding
```

## ⚖️ Legal & Ethical Notice

This tool uses only **public data** and is subject to:
- PDPA (Thai Personal Data Protection Act)
- GDPR (EU General Data Protection Regulation)
- Local privacy laws where applicable

The agent includes ethical guidelines:
- ❌ No unauthorized system bypass
- ❌ No use of leaked/private data
- ✅ Confidence scores for all findings
- ✅ User warnings for innocent targets

**Users are responsible for compliance with applicable laws.**

## 📚 Documentation

- `MODERN_UI.md` — UI/UX design notes
- `osint_agent/system_prompt.py` — Agent instructions

## 🐛 Troubleshooting

### Port already in use
```bash
streamlit run app_modern.py --server.port 8502
```

### Clear cache
```bash
rm -rf ~/.streamlit/cache
rm -rf .streamlit
```

### Test backend
```bash
python -c "from osint_agent.agent import run_osint_lookup; print('OK')"
```
