# OSINT Lookup — Agentic OSINT & Subject Intelligence Platform

เครื่องมือสืบสวน OSINT แบบ agentic สำหรับงานตำรวจ/นักวิเคราะห์: เก็บหลักฐานจากข้อมูลสาธารณะ,
สกัดโปรไฟล์, วิเคราะห์ 6D, และสร้าง Subject Intelligence Dossier ที่อ้างอิงย้อนกลับได้ทุกข้อ

> ใช้กับข้อมูลสาธารณะเท่านั้น ไม่ bypass login และไม่ใช้ข้อมูลรั่วที่ผิดกฎหมาย

## 🚀 Quick Start

```bash
pip install -r requirements.txt

# ติดตั้ง Moli (headless browser สำหรับ agent)
./scripts/install-moli.sh

# ตั้งค่า .env จาก .env.example (ต้องตั้ง OSINT_SECRET_KEY ก่อนใช้จริง)
cp .env.example .env

# ตรวจความพร้อม
python -m osint_agent.cli doctor

# CLI
python -m osint_agent.cli scan johndoe -p quick

# API + UI
python -m uvicorn osint_agent.api.app:app --port 8000
python -m streamlit run app_modern.py
```

- UI: http://localhost:8501 (เข้าสู่ระบบด้วยบัญชีด้านล่าง)
- API docs: http://localhost:8000/docs

## 🔐 ผู้ใช้และการกำหนดสิทธิ์ (demo)

ระบบมี login + RBAC เพื่อสาธิตการควบคุมการเข้าถึง ข้อมูลผู้ใช้เป็นข้อมูลจำลองใน `config/users.json`

| บัญชี | รหัสผ่าน | บทบาท | สิทธิ์ |
|---|---|---|---|
| `admin` | `Admin#1234` | admin | ทุกอย่าง + ตั้งค่า/จัดการผู้ใช้ |
| `analyst` | `Analyst#1234` | analyst | อ่าน · เริ่มสืบสวน · review · cancel |
| `viewer` | `Viewer#1234` | viewer | อ่านและส่งออกเท่านั้น |

- เปลี่ยนชุดผู้ใช้ด้วย `OSINT_USERS_FILE` (ไฟล์ JSON) และตั้ง `OSINT_SECRET_KEY` ก่อนใช้งานจริง
- รหัสผ่านเก็บเป็น PBKDF2-SHA256 + salt; token เซ็น HMAC และหมดอายุใน 8 ชั่วโมง
- API ทุกเส้นทาง (ยกเว้น `/health` และ `/auth/login`) ต้องส่ง `Authorization: Bearer <token>`
- ทุกครั้งที่ login/สำเร็จ/ล้มเหลว/logout ถูกบันทึกใน audit hash-chain
- ยัง bind localhost; หากเปิดสู่วงนอกควรเปลี่ยนรหัสผ่าน demo และใช้ HTTPS

## ⚙️ Configuration

```env
# MaxPlus (ค่าเริ่มต้น)
MAXPLUS_API_KEY=...
MAXPLUS_BASE_URL=https://api.maxplus-ai.cc/claude-cursor-full/v1/models
MAXPLUS_MODEL=claude-sonnet-5-5

# หรือ Anthropic
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_BASE_URL=
# ANTHROPIC_MODEL=

# ไม่บังคับ
HIBP_API_KEY=
OSINT_SEARCH_ENGINES=duckduckgo_html,yahoo_uk,brave
```

`MAXPLUS_*` มีลำดับความสำคัญเหนือ `ANTHROPIC_*` และตั้งค่าได้จากหน้า Settings ใน UI (เฉพาะ admin)
ถ้าไม่มี API key ระบบยังสแกนได้ด้วย deterministic fallback แต่จะไม่ใช้ LLM planner

## 🧠 หลักการทำงาน

```
Normalize → hypotheses → search → rank → fetch (Moli) → extract profile
→ leads → pivot → ownership score → 6D → Dossier
```

- **standard/deep + มี API key** → `AgentEngine` ให้ LLM เลือก action เองจาก tool ที่จำกัด
- **quick / ไม่มี key** → deterministic pipeline
- ทุกผล tool ถูกเก็บเป็น artifact พร้อม `source_url`, `output_hash`, `confidence`
- ผลค้นยังเป็น `Unverified` จนกว่าจะเปิดอ่านจริง
- LLM ห้ามสร้าง identifier เอง; validator ตัด finding ที่อ้าง evidence ไม่มีจริง

### Evidence tiers

`direct` → `derived` → `inferred` → `enrichment` และ map เป็น
`Confirmed / Probable / Possible / Unverified / Inferred / Speculative`

## 🔎 ความสามารถ

- ค้นหลาย engine ผ่าน Moli: DuckDuckGo, Yahoo, Brave, Bing, Yandex + fallback ddgs/googlesearch
- platform probe 30+ แห่ง จำแนก found / not_found / blocked / unknown
- vendor scanner: GitHub, GitLab, Reddit, Telegram, Keybase, Twitch, Medium, npm, Pinterest, X, Instagram, Facebook
- เบอร์: carrier, WhatsApp, footprint; อีเมล: HIBP, Gravatar; โดเมน: DNS, RDAP/WHOIS, Wayback
- avatar dHash, stylometry, trust anchor, BM25 evidence memory

### ชื่อไทยและครอบครัว

- แยกชื่อ/นามสกุลพร้อม source + snippet
- นามสกุลกลายเป็น pivot: ครอบครัว, พี่น้อง, บิดา, มารดา, ญาติ + จังหวัด/องค์กร
- สกัดความสัมพันธ์ที่มีคำระบุจริง (พ่อ/แม่/พี่/คู่สมรส/เพื่อนร่วมงาน) แยกจาก co-occurrence
- นามสกุลซ้ำไม่ถือเป็นหลักฐานครอบครัว

### 6D Cognitive Profiling

Identity / Geo-temporal / Psychological (OCEAN) / Technical / Ideological / OpSec
ทุกมิติมี confidence, rationale, metrics, evidence และบอก “ประเมินไม่ได้” เมื่อหลักฐานไม่พอ
OCEAN เป็นสมมติฐานจากสถิติข้อความ ไม่ใช่แบบทดสอบจิตวิทยา

## 🖥️ UI

แท็บ: บุคคลนี้คือใคร · ตัวระบุที่พบ · โปรไฟล์ · 6D · ความสัมพันธ์ · Timeline · รายงาน · Agent actions · หลักฐาน · Candidates · ผัง · ส่งออก

กด “วิเคราะห์ต่อ” ที่ตัวระบุ/นามสกุลเพื่อสร้าง child run ที่ผูก `parent_run_id`

## 🖥️ CLI

| คำสั่ง | ใช้ทำอะไร |
|---|---|
| `doctor` | ตรวจความพร้อม (รวม Moli) |
| `scan <target> -p quick\|standard\|deep` | สแกนและแสดงผล |
| `agent <target>` | รัน standard |
| `resume <run_id>` | ทำต่อจาก checkpoint |
| `export <run_id> -o out.json` | ส่งออกหลักฐาน |
| `export <run_id> --research --docx -o r.docx` | รายงานวิจัยตาม template |
| `review <run_id> --candidate c1 --action confirm` | ตัดสิน candidate |

## 🔌 API

ทุกเส้นทางยกเว้น `/health` และ `/auth/login` ต้องส่ง `Authorization: Bearer <token>`

| Method | Path | สิทธิ์ |
|---|---|---|
| POST | `/auth/login` | สาธารณะ |
| GET | `/auth/me` | ทุกบทบาท |
| GET | `/auth/users` | admin |
| POST | `/auth/logout` | ทุกบทบาท |
| POST | `/investigate` | analyst/admin |
| GET | `/runs`, `/runs/{id}` | ทุกบทบาท |
| GET | `/runs/{id}/events` (SSE) | ทุกบทบาท |
| GET | `/runs/{id}/analysis`, `/report`, `/findings`, `/candidates` | ทุกบทบาท |
| POST | `/runs/{id}/pivot` | analyst/admin |
| GET | `/runs/{id}/research-report` (`?format=docx`) | ทุกบทบาท |
| POST | `/runs/{id}/review` | analyst/admin |
| POST | `/runs/{id}/cancel` / `/resume` | analyst/admin |

```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"analyst","password":"Analyst#1234"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -H "Authorization: Bearer $TOKEN" localhost:8000/runs
```

## 📁 โครงสร้าง

```
osint_agent/
├── api/                  # FastAPI + SSE + auth endpoints
├── auth.py               # login, PBKDF2, token HMAC, RBAC
├── services/             # agent engine, orchestrator, budget, store, trust anchor
├── profiling/            # corpus, extractor, resolver, 6D, synthesizer, research report
├── tools/                # 22 tools (lazy import)
├── knowledge/            # playbooks + anti-hallucination
├── core/                 # evidence schema + hash
└── cli.py
config/users.json         # ผู้ใช้จำลองสำหรับ demo
docs/                     # คู่มือ, use case, หลักฐานทดสอบ
vendor/                   # SYNINT core + osint-d2 adapters (ดู VENDORED.md)
```

## 🧪 Tests

```bash
make test          # 228 กรณี ไม่ยิงเน็ต (รวม auth/RBAC 12 กรณี)
make lint
```

## ⚖️ ข้อจำกัดและจริยธรรม

- ข้อมูลสาธารณะเท่านั้น; หน้า blocked คือ “ตรวจไม่ได้” ไม่ใช่ “ไม่พบ”
- PDPA: ไม่รายงานพิกัดบ้าน real-time, เลขบัตร, ทะเบียนรถเต็ม
- ไม่ auto-merge ตัวตน — identity candidate ต้องผ่าน human review
- “ไม่พบข้อมูล” ไม่เท่ากับ “ปลอดภัย”
- มี login + RBAC สำหรับ demo แต่ผู้ใช้เป็นข้อมูลจำลอง ยังไม่เชื่อม AD/LDAP
- ยัง bind localhost; หากเปิดสู่วงนอกต้องเปลี่ยนรหัสผ่านและใช้ HTTPS

เอกสารเพิ่มเติม: `docs/USER_MANUAL.md`, `docs/USE_CASES.md`, `docs/TEST_EVIDENCE.md`, `ARCHITECTURE.md`, `THREAT_MODEL.md`, `DPIA.md`, `VENDORED.md`
