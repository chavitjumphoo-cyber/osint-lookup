# Architecture

## ชั้นการทำงาน (lead-driven profiling)

```
Normalize → hypotheses → search → rank → fetch → extract → leads → pivot
                                              ↓
                                     profiling corpus
                                              ↓
                          profiles / entities / timeline / contradictions
                                              ↓
                                  Subject Intelligence Dossier
```


```
CLI / REST+SSE / Streamlit (thin client)
              │
      services/orchestrator
              │
  playbook + budget + trust_anchor + evidence_memory
              │
        tools/ (22 tools, lazy import)
              │
  core/evidence (schema, hash, untrusted wrap)
              │
      services/store (SQLite: run/event/step/evidence/artifact/report)
              │
      vendor/ (SYNINT core + osint-d2 adapters)
```

## หลักการ

1. **หลักฐานมาก่อนข้อสรุป** — tool ทุกตัวคืน `status` + `output_hash` + `evidence`
2. **แยกชั้นหลักฐาน** — `direct` / `derived` / `inferred` / `enrichment` และ map เป็น confidence vocabulary
3. **ไม่ auto-merge** — identity candidate ต้องผ่าน human review (`POST /runs/{id}/review`)
4. **checkpoint** — step ที่ `done` ถูกข้ามเมื่อ resume
5. **untrusted** — เนื้อหาเว็บถูกห่อ `<untrusted_data>` ก่อนเข้า LLM
6. **เพดานทรัพยากร** — budget ต่อ profile และ per-run

## สัญญา tool

```
{tool, endpoint, status, result, output_hash, evidence[], images[]}
status ∈ ok | empty | blocked | unknown | failed
```

`blocked` = ตรวจไม่ได้, `empty` = ตรวจแล้วไม่พบ — รายงานต้องแยกสองอย่างนี้

## AgentEngine v2

standard/deep + มี API key → `services/agent_engine.py`:
LLM เลือก action → `agent_tools` → evidence core → artifact → profile extractor → leads
ทุก action บันทึก reason/result; ไม่มี key → deterministic fallback

## Profiling corpus

`profiling/` เก็บ artifact ทุกชิ้นพร้อม source_url, source_type, output_hash และ confidence
แล้วสกัดเป็น entity → profile → relationships/timeline → synthesizer
ผลค้นยังเป็น Unverified จนกว่าจะเปิดอ่านจริง

## Playbooks

`knowledge/playbooks/*.yaml` กำหนด trigger, steps, anti-patterns, stop conditions, max_steps
`services/skills.py` เลือกตาม target type และตัด step ตาม profile

## Evidence / report

`core/evidence.py` สร้าง EvidenceItem (deterministic id), sha256 hash, และ wrap untrusted
`services/report_builder.py` สร้างรายงานที่มี findings + confidence + hash + limitations บังคับ

## Vendor

`vendor/synint` = evidence registry, identity resolution, scoring, contradiction, checkpoint
`vendor/osint_d2` = scanners, trust anchor, vector store, SSRF guard, rate limiter
`vendor/_compat.py` แปลง config เป็น Anthropic client

## Run store

`audit/runs.sqlite` เก็บ runs, events, steps, evidence, candidates, reports
ใช้ `osint export <run_id>` เพื่อย้ายงานไปตรวจที่อื่น

## API

| Method | Path | หมายเหตุ |
|---|---|---|
| POST | `/investigate` | 202 + run_id |
| GET | `/runs/{id}` | สถานะ |
| GET | `/runs/{id}/events` | SSE |
| GET | `/runs/{id}/report` | markdown |
| GET | `/runs/{id}/findings` | หลักฐานดิบ |
| POST | `/runs/{id}/review` | confirm/reject/reverse |
| POST | `/runs/{id}/cancel` | ยกเลิก |
| POST | `/runs/{id}/resume` | ทำต่อจาก checkpoint |
