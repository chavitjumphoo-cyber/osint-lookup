# OSINT Lookup — Intelligence-Grade Investigation Platform

AI-powered OSINT tool for comprehensive identity research across 30+ platforms using ReAct agent pattern.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env (ดู .env.example)

# CLI
python -m osint_agent.cli doctor
python -m osint_agent.cli scan johndoe -p quick

# REST + SSE API
python -m uvicorn osint_agent.api.app:app --port 8000
curl -X POST localhost:8000/investigate -H 'content-type: application/json' \
  -d '{"target":"johndoe","profile":"quick"}'

# Streamlit (thin client)
python -m streamlit run app_modern.py
```

เปิด API docs ที่ **http://localhost:8000/docs** หรือ Streamlit ที่ **http://localhost:8501**

## 🖥️ CLI

| คำสั่ง | ใช้ทำอะไร |
|---|---|
| `doctor` | ตรวจความพร้อมของเครื่อง |
| `scan <target> -p quick` | สแกนและแสดงผลทันที (profile: quick/standard/deep) |
| `agent <target>` | รันด้วย profile standard |
| `resume <run_id>` | ทำ run เดิมต่อจาก checkpoint |
| `export <run_id> -o out.json` | ส่งออกหลักฐาน |
| `export <run_id> --research --docx -o r.docx` | ออกรายงานวิจัยตาม template |
| `review <run_id>` | ตรวจหลักฐาน/candidate |
| `review <run_id> --candidate c1 --action confirm` | ตัดสิน candidate |

เพิ่ม `--db path.sqlite` หน้า subcommand เพื่อแยกฐาน run

## ⚙️ Configuration

### .env File

```env
# MaxPlus (แนะนำ)
MAXPLUS_API_KEY=...
MAXPLUS_BASE_URL=https://api.maxplus-ai.cc/claude-cursor-full/v1/models
MAXPLUS_MODEL=claude-sonnet-5-5

# หรือ Anthropic
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_BASE_URL=
# ANTHROPIC_MODEL=
```

`MAXPLUS_*` มีลำดับความสำคัญเหนือ `ANTHROPIC_*` และตั้งค่าได้จากหน้า Settings ใน UI

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
    ├── cli.py                 # CLI (doctor; scan/agent/resume ตาม Phase 2)
    ├── tools/                 # OSINT tools แยกหมวด + lazy import
    ├── platform_scanner.py    # 30+ platform scanner (found/not_found/blocked/unknown)
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

## 🧠 Profiling

- lead-driven corpus → profile resolver → 6D Cognitive Profiling
- ทุกข้อค้นพบอ้าง artifact id + URL + hash; OCEAN เป็นสมมติฐานจากสถิติข้อความ
- Dossier 14 หัวข้อ + 6D ทุกมิติ และรายงานวิจัยแยกสำหรับส่งอาจารย์/หน่วยงาน

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
- **Search**: multi-engine ผ่าน Moli (DuckDuckGo/Yahoo/Brave/Bing/Yandex) — ไม่ใช้ API key
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

### ตรวจความพร้อมของเครื่อง
```bash
python -m osint_agent.cli doctor
```

### Test backend
```bash
make test        # ไม่ยิงเน็ต
make test-network
```
