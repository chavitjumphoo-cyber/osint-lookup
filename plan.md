# แผนพัฒนา: Agentic OSINT ที่ใช้งานได้จริง

> สถานะ: เสร็จครบ Phase 0–6 (145 tests, ruff clean)
> ขอบเขต: ครบ Phase 0–6 · ผู้ให้บริการ LLM: Claude/MaxPlus เท่านั้น · วิธี: vendor โค้ดจาก repo อ้างอิง · เคสเป้าหมาย: บุคคล/โปรไฟล์สังคม, มิจฉาชีพ/บัญชีม้า/เบอร์, อีเมล/บัญชีรั่ว, โดเมน/เว็บฟิชชิ่ง · รูปแบบผลิตภัณฑ์: CLI + API เป็นหลัก, Streamlit เป็น thin client

---

## 1. บริบทและเหตุผล

โปรเจกต์ปัจจุบันเป็น ReAct agent เดี่ยวที่ต่อ Anthropic ตรง + Streamlit UI มีจุดแข็งเฉพาะตัว (system prompt สายสืบสวนไทย, `verify_official`, audit hash-chain, SSRF guard, rate limiter) แต่ยังขาดกลไกพื้นฐานของการสืบสวนจริง: ไม่มี evidence store, ไม่มี provenance, ไม่มี trust anchor, ไม่มีตัวตัด false positive, ไม่มี checkpoint, ไม่มี CLI/API ให้ agent อื่นเรียกใช้

repo อ้างอิงทั้งสามให้กลไกที่ขาดนี้ได้:

| แหล่ง | กลไกที่นำมาใช้ |
|---|---|
| `gs-ai/SYNINT` | `InvestigationContext`, `EvidenceItem` + deterministic ID + evidence tier, `EvidenceRegistry`/`EntityRegistry` (dedupe/merge), identity candidate workflow ที่บังคับ human review, contradiction detection, evidence scoring, checkpoint/resume, SQLite investigation store, chain-of-custody |
| `Doble-2/osint-d2` | Trust anchors + reference identity + weighted profile scoring + hard contradiction, BM25 evidence memory, forced `emit_report`, untrusted-data wrapping, per-platform scanner modules, profile enricher, url guard, rate limiter |
| `frangelbarrera/osint-agent-skills` | Pivot playbooks (trigger/steps/anti-patterns/stop conditions), confidence vocabulary, anti-hallucination rules, report template ที่บังคับ Pivots + Limitations, output integrity hash |

### สิทธิ์การใช้งาน

- `osint-d2` — MIT: vendor ได้ ต้องแนบ `LICENSE.osint-d2` และระบุที่มา
- `osint-agent-skills` — MIT: แปลงเนื้อหาเป็น YAML/Markdown พร้อมระบุที่มา
- `SYNINT` — **ไม่มีไฟล์ license**: vendor โค้ดพร้อม `VENDORED.md` ระบุ commit + URL และต้องแจ้งเจ้าของก่อนเผยแพร่สาธารณะ

---

## 2. ผลตรวจสภาพปัจจุบัน (baseline)

### บั๊กที่ทำให้ระบบใช้ไม่ได้

| ไฟล์ | ปัญหา | ผลกระทบ |
|---|---|---|
| `tools.py:28` | `from googlesearch import search` แต่ไม่มีใน `requirements.txt` | import พังทั้งโมดูล → test ทั้งชุด collect ไม่ได้ |
| `tools.py:904` | ใช้ `result.associated_names` แต่ dataclass คือ `discovered_names` | `scan_phone_advanced` error ทุกครั้ง |
| `platform_scanner.py:49` | นับ `status_code == 200` เป็น "พบโปรไฟล์" | Facebook/Instagram/X คืน 200 ทุกกรณี → false positive จำนวนมาก |
| `platform_scanner.py:125` | วน `requests` ทีละตัว + `sleep(0.5)` | ช้า และไม่ parallel ตามที่ README อ้าง |
| `agent.py:157` | สร้าง `IdentityTriangulator()` แล้วไม่เคยใช้ | dead code, ไม่มีการ triangulate จริง |
| `agent.py` | ไม่มี evidence store / trust anchor / contradiction / checkpoint | ReAct 16 ก้าวจบ แยกข้อเท็จจริงกับข้อสันนิษฐานไม่ได้ |
| `app_modern.py` | ไม่มี evidence log ให้ตรวจย้อนกลับ | รายงานตรวจสอบไม่ได้ |

### หลักฐานการรัน

```
$ .venv/bin/python -c "from osint_agent.tools import execute_tool"
ModuleNotFoundError: No module named 'googlesearch'

$ .venv/bin/python -m pytest -q
ERROR tests/test_tools.py — ModuleNotFoundError: No module named 'googlesearch'
1 error in 0.44s
```

---

## 3. หลักการออกแบบ

1. **หลักฐานก่อนข้อสรุป** — ทุก finding ต้องมี `evidence_id` + `source_reference` + `output_hash`
2. **แยกชั้นข้อมูล** — `direct evidence` / `derived` / `inferred` / `enrichment only` ห้ามปนกันในรายงาน
3. **ไม่ auto-merge ตัวตน** — identity candidate ต้องมีสถานะ CANDIDATE → REVIEWED → CONFIRMED/REJECTED
4. **ทนต่อความล้มเหลว** — tool ใดพังต้องไม่ลากทั้ง run, และต้องแยก "ตรวจไม่ได้" ออกจาก "ไม่พบ"
5. **เนื้อหาเว็บเป็น untrusted** — wrap ด้วย `<untrusted_data>` ก่อนเข้าโมเดล
6. **ทุก run ตรวจย้อนกลับได้** — checkpoint, ledger, evidence hash, เวอร์ชัน tool
7. **จุดขายไทยคงไว้** — `verify_official` + ฐานหน่วยงาน, audit chain, SSRF guard
8. **ไม่ over-collect** — budget ต่อ run และ stop condition ต่อ playbook

---

## 4. สถาปัตยกรรมเป้าหมาย

```
CLI / REST+SSE / Streamlit (thin client)
                │
        services/orchestrator.py
                │
   ┌────────────┼─────────────┬──────────────┐
   │            │             │              │
 budget     skills        trust_anchor   evidence_memory
   │            │             │              │
   └────────────┴──── tools/ ┴──────────────┘
                │
        core/{context,schemas,registries,store,checkpoint,validate}
                │
        vendor/{synint,osint_d2}
```

### โครงสร้างไฟล์เป้าหมาย

```
osint_agent/
├── cli.py
├── api/{app,routes,ws,schemas}.py
├── services/
│   ├── orchestrator.py
│   ├── budget.py
│   ├── skills.py
│   ├── trust_anchor.py
│   ├── evidence_memory.py
│   ├── evidence_log.py
│   ├── scoring.py
│   ├── contradiction.py
│   └── report_builder.py
├── core/
│   ├── context.py
│   ├── schemas.py
│   ├── registries.py
│   ├── store.py
│   ├── checkpoint.py
│   ├── validate.py
│   ├── identity_resolution.py
│   └── entity_utils.py
├── knowledge/
│   ├── playbooks/{phone,email,username,domain,photo,breach}.yaml
│   ├── methodologies/
│   └── ethics/anti_hallucination.md
├── tools/
│   ├── registry.py
│   ├── phone.py
│   ├── email.py
│   ├── username.py
│   ├── web.py
│   ├── domain.py
│   └── forensics.py
├── agent.py            # orchestrator entry ที่ CLI/API/UI เรียก
├── system_prompt.py    # เขียนใหม่
└── report_export.py    # template ใหม่
vendor/
├── synint/
├── osint_d2/
VENDORED.md
LICENSE.osint-d2
```

---

## 5. แผนดำเนินงาน

### Phase 0 — Stabilize (ต้องผ่านก่อนทุกอย่าง) — เสร็จแล้ว

- [x] เพิ่ม dependency: `googlesearch-python`, `httpx`, `pillow`, `pytest`, `pytest-asyncio`, `fastapi`, `uvicorn`, `typer`, `pydantic`, `pyyaml`
- [x] แก้บั๊กชื่อฟิลด์ `discovered_names` / `associated_names`
- [x] แตก `tools.py` เป็น `tools/` package, import แบบ lazy ต่อ tool
- [x] เขียน `platform_scanner` ใหม่: probe rule ต่อแพลตฟอร์ม, async, dedupe, แยก `unknown`/`blocked` ออกจาก `not_found`
- [x] ลบ `identity_triangulation.py` (แทนด้วย `core/identity_resolution.py`)
- [x] เพิ่ม `pyproject.toml` (ruff + pytest config) และ Makefile target `lint`, `test`
- [x] **เกณฑ์ผ่าน:** `pytest` 79 passed · `execute_tool("scan_phone_advanced", …)` คืนผลจริง · `python -m osint_agent.cli doctor` รันได้

### Phase 1 — Vendor foundation — เสร็จแล้ว

- [x] `vendor/synint/` จาก commit `30250174` — core (context/schemas/registries/investigation_db/checkpointing/validation/entity_utils/identity_resolution) + agents (base/_pipeline/_shared/evidence_scoring/contradiction/entity_resolution)
- [x] `vendor/osint_d2/` จาก commit `5f40bb79` — osint_sources 20 ตัว, email_sources, profile_enricher, specific_scrapers, trust_anchor, vector_store, url_guard, rate_limiter, sherlock_runner, http_client, config
- [x] `vendor/_compat.py` เชื่อม config โปรเจกต์ → `AppSettings` และคืน Anthropic client (ไม่พึ่ง OpenAI SDK)
- [x] แนบ `LICENSE.osint-d2`, `VENDORED.md` (URL, commit, วันที่, รายการไฟล์, สิ่งที่แก้)
- [x] **เกณฑ์ผ่าน:** import vendor ครบทุกโมดูล · test 12 รายการผ่าน · scanner GitHub ทำงานผ่าน compat

### Phase 2 — Service layer + CLI/API — เสร็จแล้ว

- [x] `services/orchestrator.py` ถือ `InvestigationContext` + run store + checkpoint (resume ข้าม step ที่ done)
- [x] `services/budget.py` จำกัด step / tool call / เวลา / ขนาดผล ต่อ profile
- [x] `services/store.py` เก็บ run/event/step/finding ใน SQLite (เป็น checkpoint)
- [x] `cli.py`: `scan`, `agent`, `resume`, `export`, `review`, `doctor`
- [x] `api/app.py`: `POST /investigate`, `GET /runs/{id}`, `GET /runs/{id}/events` (SSE), `POST /runs/{id}/cancel`, `POST /runs/{id}/resume`, export
- [x] pydantic model ทุก request/response + error envelope มาตรฐาน
- [x] **เกณฑ์ผ่าน:** เรียก API จริงแล้วได้รับ event stream และ findings โดยไม่ต้องเปิด Streamlit · 113 tests ผ่าน

### Phase 3 — Evidence discipline — เสร็จแล้ว

- [x] tool ทุกตัวคืน `ToolOutcome` (status/output_hash/evidence) ผ่าน `services/tool_runner.py` + `core/evidence.py`
- [x] `knowledge/playbooks/*.yaml` 6 ชุด + `knowledge/ethics/anti_hallucination.md`
- [x] `services/skills.py` เลือก playbook, บังคับ step ตาม profile, ฉีด prompt block
- [x] เขียน `system_prompt.py` ใหม่ตาม confidence vocabulary + cite-or-retract + tool-failure vs empty
- [x] `services/report_builder.py` + report ที่มี findings/confidence/hash/limitations บังคับ
- [x] tool `verify_output_integrity` + เก็บ `output_hash` ทุก finding
- [x] **เกณฑ์ผ่าน:** evidence id/hash ครบ · tamper ตรวจจับได้ · รายงานมี limitations ทุกฉบับ

### Phase 4 — Trust anchor / ตัด false positive — เสร็จแล้ว

- [x] `services/trust_anchor.py`: reference identity + คะแนน name/bio/avatar/location + hard contradiction
- [x] CLI `--trust` / API `trusted[]` / Streamlit ช่อง Verified accounts
- [x] `services/evidence_memory.py` BM25 + tool `search_evidence`
- [x] บังคับ report ท้ายงาน (`_emit_report`) แม้หมด budget
- [x] wrap ผลภายนอกด้วย `<untrusted_data>` + escape
- [x] **เกณฑ์ผ่าน:** ทดสอบจริง torvalds ตัด Facebook "Patrick" และ Pinterest ออกพร้อมเหตุผล

### Phase 5 — Pipeline + ขยาย tool — เสร็จแล้ว

- [x] pipeline `quick | standard | deep` ผ่าน playbook
- [x] specialist: `identity_candidate`, `contradiction`, `evidence_scoring`, `timeline`, `emit_report`
- [x] คิว human review: `POST /runs/{id}/review`, CLI `review --candidate --action`
- [x] tool ใหม่: DNS, RDAP/WHOIS, Wayback CDX, GitHub intel, Gravatar, `search_evidence`, `verify_output_integrity`
- [x] cache ผ่าน SQLite store + per-run budget + สถานะ blocked
- [x] **เกณฑ์ผ่าน:** deep domain ใช้ whois/wayback/dns และสร้างรายงานครบ

### Phase 6 — Streamlit + hardening + docs — เสร็จแล้ว

- [x] `app_modern.py` เป็น thin client เรียก orchestrator + tabs หลักฐาน/candidate/รีวิว
- [x] `ARCHITECTURE.md` ใหม่, `THREAT_MODEL.md`, `DPIA.md`
- [x] เอกสาร CLI/API/trust ใน README
- [x] **เกณฑ์ผ่าน:** 145 tests ผ่าน, ruff clean, UI/CLI ใช้ run store เดียวกัน

---

## Phase 7 — ถอด Google API + Moli (เสร็จแล้ว)

- [x] migration `findings.status/output_hash` + regression test
- [x] ถอด `GOOGLE_API_KEY`/`GOOGLE_CX` ทั้ง UI/env/agent/เอกสาร
- [x] ติดตั้ง Moli v1.1.21 + `scripts/install-moli.sh` + doctor check
- [x] `services/browser.py` Moli → requests fallback, block private, timeout
- [x] `services/search_engines.py` multi-engine + fallback ddgs → googlesearch
- [x] tool `web_search` + alias `google_search`, อัปเดต playbook
- [x] docs: threat model/DPIA/README

---

## 6. สัญญา tool (บังคับ)

```python
{
  "tool": "phone_info",
  "endpoint": "local:libphonenumber",
  "status": "ok",              # ok | empty | blocked | failed
  "evidence": [EvidenceItem],
  "result": "ข้อความสำหรับโมเดล",
  "output_hash": "sha256:…",
  "started_at": "ISO8601",
  "duration_ms": 123,
}
```

- `blocked` แปลว่าโดนกัน bot/ต้องล็อกอิน → รายงานว่า "ตรวจไม่ได้"
- `empty` แปลว่าตรวจสำเร็จแต่ไม่พบ → รายงานว่า "ไม่พบ" เท่านั้น
- ห้าม tool ใด raise ออกนอก `execute_tool`

---

## 7. การทดสอบ

| ชั้น | วิธี |
|---|---|
| unit | `pytest` ต่อ tool ด้วย fixture HTML (ไม่ยิงเน็ต) |
| contract | ทุก tool ต้องผ่าน schema validator + hash ตรง |
| integration | run จริงแบบ marker `@pytest.mark.network` |
| regression | เคส 4 ประเภท × 3 run, ตรวจว่า false positive ไม่เกินเกณฑ์ |
| CLI/API | subprocess + httpx client |

ตัวชี้วัด:
- 0 import error, 0 unhandled tool exception
- 100% ของ finding มี source
- false positive ของ platform scan < 10% บนชุดตรวจมือ
- ทุก run resume ได้จาก checkpoint

---

## 8. ความเสี่ยงและมาตรการ

| ความเสี่ยง | มาตรการ |
|---|---|
| SYNINT ไม่มี license | ทำ `VENDORED.md` ระบุที่มา และขออนุญาตก่อน public release |
| vendor ผูก Python 3.11+/OpenAI SDK | `_compat.py` แปลงเป็น Anthropic, ตั้ง `requires-python = ">=3.11"` |
| scan โดนบล็อก | fallback sherlock/maigret + สถานะ `blocked` |
| trust anchor ผิด → recall ต่ำ | หน้าแสดงโปรไฟล์ที่ถูกตัด + ปุ่ม override |
| LLM แต่งข้อมูล | anti-hallucination playbook + `verify_output_integrity` + cite-or-retract |
| ขยาย tool มากเกิน | budget, cache, per-host limit, ปิด tool ที่ไม่ใช้ใน playbook |

---

## 9. สิ่งที่คงไว้

- `verify_official` + `OFFICIAL_ENTITIES` (ฐานหน่วยงานไทย)
- audit hash-chain ใน `access.py` (ต่อยอดเป็น chain-of-custody)
- SSRF guard และ `DomainRateLimiter`
- หลัก "ไม่พบ ≠ ปลอดภัย"

## 10. สิ่งที่เลิกใช้

- `identity_triangulation.py` (แทนด้วย identity resolution ของ SYNINT)
- ลูป ReAct เดี่ยวใน `agent.py` (แทนด้วย orchestrator + pipeline)
- การอ่านค่าจาก environment แบบ global ใน tool (เปลี่ยนเป็น context)

---

# Phase 8 — ปรับให้เป็นการทำ Profiling ที่ได้ข้อมูลจริง

> สถานะ: วางแผน (ยังไม่ลงมือ) — เกิดจากทดลองใช้แล้วพบว่ารายงานเป็น "รายการ evidence" ไม่ใช่แฟ้มประวัติ และการเก็บข้อมูลแบนเกินไป

## ปัญหาที่พบจากการใช้งานจริง

1. **ไม่มีขั้นสกัดข้อมูลIdentifying จากหน้าเว็บ** — `fetch_page` ได้ข้อความดิบ แต่ไม่มีใครสกัดชื่อที่แสดง, bio, สถานที่, อาชีพ, ความสนใจ ออกมาเป็นโครงสร้าง
2. **ไม่มีขั้นอ่านผลค้น** — `web_search` คืน title/url/snippet แล้วจบ ทั้งที่ title/snippet มีชื่อและบริบท
3. **ไม่เคยเปิดหน้าโปรไฟล์ที่ค้นเจอ** — playbook ไม่มี step `fetch_page` ของผลค้น จึงไม่มีข้อมูลเชิงลึก
4. **query แบน** — `_args` ใช้ `_"target"_` ซ้ำทั้งงาน (เช่น `""unittest python""`), ไม่มี variants ของเบอร์/username, ไม่มี site: dork, ไม่มีคำ scam ไทย
5. **ไม่มี planner แบบ LLM** — orchestrator วิ่งตาม playbook ตายตัว ไม่ pivot ตามสิ่งที่เจอ (ความสามารถเดิมของ agent หายไป)
6. **รายงานไม่ใช่ profiling** — เป็น Finding 1..N ตามชนิด identifier ไม่มีหัวข้อตัวตน/เครือข่าย/วิถีชีวิต/6D ตาม prompt เดิม
7. **prompt เดิม (Subject Intelligence Dossier + 6D) ถูกแทนที่ด้วย prompt วินัยสั้น ๆ** — ต้องรวมกลับ
8. **platform_scanner ยังใช้ httpx ตรง** — ไม่ใช้ Moli จึงติด 200/blocked และไม่สกัดชื่อ/bio/รูป
9. **`llm_polish` ไม่ถูกเรียก** — รายงานไม่เคยถูกเรียบเรียงด้วยโมเดล
10. **ข้อมูลซ้ำ/หลอกตา** — evidence จาก URL ของ search result ถูกนับเป็น "หลักฐาน" ทั้งที่ยังไม่ได้เปิดอ่าน

## เป้าหมาย

ให้ผลลัพธ์เป็น **Subject Intelligence Dossier** ที่มีข้อมูลใช้ได้จริง: ชื่อที่แสดง, bio, พื้นที่, อาชีพ, ความสนใจ, ความเชื่อมโยง — ทุกข้อมี source และ confidence — ไม่ใช่ list ของ URL

## แผนงาน

### 8.1 แก้บั๊กพื้นฐานก่อน
- `_q()`: ใส่ quote ครั้งเดียว (ปัจจุบันได้ `""target""`)
- ลบ dead code: `PhoneScanResult` ส่วนที่ไม่มีวันรันใน `advanced_tools.scan_phone`, `SPECIALISTS`/`_registry` ที่ไม่ใช้
- แยก `web_search` กับ `fetch_page` ให้ evidence tier ต่างกัน: ผลค้น = `derived` (ยังไม่อ่าน), หน้าเว็บที่เปิดแล้ว = `direct`

### 8.2 Recon query builder (`services/recon.py`)
- สร้าง query จาก target ตามชนิด:
  - เบอร์: ทุกรูปแบบ (E.164, national, ไม่มีขีด) × คำ `มิจฉาชีพ|โกง|scam|บัญชีม้า` + site dork (facebook, pantip, twitter)
  - username: username เปล่า, `"username" site:<platform>` จากผล scan, ชื่อที่พบ
  - ชื่อ: ชื่อเต็ม/ชื่อเล่น/สะกดต่าง + อาชีพ/จังหวัดถ้ามี
  - อีเมล/โดเมน: ตัวตรง + breach/WHOIS context
- จำกัด query ต่อรอบตาม budget, กัน query ซ้ำด้วย hash
- **ไม่นับ URL จาก search เป็นหลักฐานจนกว่าจะถูกดึง**

### 8.3 ตัวสกัดโปรไฟล์ (`services/profile_extract.py`)
- จาก title/snippet และ HTML ที่ fetch: สกัด
  - display name, ชื่อเล่น, bio, พื้นที่, ที่ทำงาน/สถานศึกษา, ลิงก์ภายนอก, interest keywords, ภาษา
  - เบอร์/อีเมล/handle ที่ปรากฏใน bio
- กติกา: ทุกฟิลด์ต้องมี `source_url` + `snippet` + confidence; ห้ามเดาจากชื่อ user
- ใช้ LLM สกัดเฉพาะเมื่อมี key, fallback regex

### 8.4 อ่านเชิงลึกอัตโนมัติ (`services/deep_read.py`)
- เลือก URL ที่น่าอ่านจากผลค้น (กรอง aggregator/โลโก้/หน้าล็อกอิน)
- เปิด 3–5 หน้าแรกด้วย `fetch_page` แบบขนาน (semaphore, budget)
- เรียก `profile_extract` กับทุกหน้า, เก็บเป็น profile records
- ลิงก์ที่ blocked → รายงานว่าตรวจไม่ได้ ไม่ทิ้งเงียบ

### 8.5 Platform scanner ผ่าน Moli (`platform_scanner.py`)
- เปลี่ยนการ probe เป็น `browser.fetch_json` แทน httpx
- ถ้าเจอ 200: ดึง `title`, meta description, og:title/og:image, bio จาก HTML
- คำนวณ ownership signal: username ตรง + ชื่อ/bio/รูปตรงกับ anchor
- สถานะเดิม stuck ที่ unknown ให้ลดลง: มี marker ใน DOM → found พร้อมข้อมูล; ไม่มี → unknown

### 8.6 LLM Planner/Agent (`services/llm_agent.py`)
- คืนลูป ReAct เดิม: system prompt เต็ม + tools + ประวัติ + budget
- planner เลือก tool เอง, orchestrator เก็บ evidence/hash ทุกครั้ง
- บังคับ `emit_report` เมื่อครบ budget
- ใช้ได้เฉพาะเมื่อมี ANTHROPIC key; ไม่มี key ใช้ deterministic plan เดิม
- tool whitelist ตาม playbook ต่อรอบ

### 8.7 Profiler + รายงาน Dossier (`services/profiler.py`, `report_builder.py`)
- สร้าง model กลาง `Profile` (names, aliases, handles, phones, emails, orgs, locations, interests, relations, geo/time, tech, opsec)
- `report_builder` เปลี่ยนเป็นหัวข้อตาม prompt เดิม:
  1. Identity & Digital Identifiers
  2. Associate & Family Network
  3. Lifestyle & Behavioral Insights + 6D
  4. Investigative Notes / Pivot Points
  5. Fraud history
  6. Limitations + evidence sources (hash)
- เรียก `llm_polish` เมื่อมี key (ปัจจุบันมีแต่ไม่ถูกเรียก) พร้อมห้ามเพิ่ม identifier
- ส่วน evidence ดิบย้ายไปภาคผนวก

### 8.8 Prompt
- รวม prompt เดิม (Dossier schema + 6D + กติกาภาพ) กลับมา
- คงส่วนใหม่: confidence vocabulary, cite-or-retract, tool-failure vs empty, untrusted
- เพิ่มกติกา profiling: แยกบัญชีหลัก/รอง, ห้ามสรุปนิสัยจากโพสต์เดียว

### 8.9 Playbook
- เพิ่ม step `deep_read` และ `profile_extract` ใน playbook ทุกชนิด (standard/deep)
- `deep` เพิ่ม reverse image/avatar compare เมื่อมีรูป
- ระบุ stop condition: ได้ฟิลด์ครบ 5 หมวด หรือ budget หมด

### 8.10 เครื่องมือใหม่
- `fetch_profile(url)` — เปิดหน้าและสกัดโปรไฟล์ในครั้งเดียว
- `extract_profile(text, source_url)` — สกัดจากข้อความที่ได้แล้ว
- `compare_avatar_set(urls)` — เทียบรูปหลายรูปกับ anchor
- คง tool เดิมทั้งหมด

## เกณฑ์ผ่าน
- เคสทดสอบจริง 3 แบบ (username ที่มีตัวตน, เบอร์ไทย, ชื่อบุคคล) ต้องมีอย่างน้อย:
  - display name หรือ bio จากหน้าจริง ≥ 1 รายการ
  - ฟิลด์โปรไฟล์ ≥ 3 หมวด
  - ทุกฟิลด์มี source URL + confidence
  - รายงานมีหัวข้อ Dossier ครบและ Limitations
- ไม่มี `""query""`, ไม่มี URL ผลค้นถูกนับเป็น direct evidence
- `pytest` เขียว, `ruff` clean

## ความเสี่ยง
- LLM planner มีต้นทุน/ช้า → จำกัด step และใช้เฉพาะ standard/deep
- หน้าเว็บส่วนใหญ่บล็อก → ต้องรายงาน blocked ไม่ใช่ปลอมข้อมูล
- การสกัดชื่อผิด → confidence + human review + ห้าม merge
