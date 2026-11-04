# Vendored code

โค้ดในโฟลเดอร์ `vendor/` ถูกคัดลอกมาจากโปรเจกต์ต้นทางเพื่อนำกลไกที่ผ่านการออกแบบมาแล้วมาใช้
ทุกไฟล์ระบุ commit ไว้แน่นอน ห้ามแก้ต้นทางในเครื่องโดยไม่อัปเดตเอกสารนี้

## gs-ai/SYNINT

- URL: https://github.com/gs-ai/SYNINT
- Commit: `30250174dff5152bf2827c426fb18b8ae43d48f6`
- วันที่ดึง: 2026-11-04
- License: **ไม่มีไฟล์ LICENSE ใน repo** (ต้องขออนุญาตก่อนเผยแพร่สาธารณะ)
- ไฟล์:
  - `vendor/synint/core/{context,schemas,registries,investigation_db,checkpointing,validation,entity_utils,identity_resolution}.py`
  - `vendor/synint/agents/{base_agent,_pipeline,_shared,evidence_scoring_agent,contradiction_detection_agent,entity_resolution_agent}.py`

### สิ่งที่แก้

- เปลี่ยน import สัมพัทธ์แบบ top-level (`from core.*`, `from agents.*`) เป็น absolute ภายใต้ `vendor.synint.*`
- เพิ่ม `__init__.py` ให้เป็น package
- `agents/_shared.py`: เพิ่ม `is_email`, `is_phone` และตรวจจับ `email`/`phone` ใน `infer_target_types`
- `core/context.py`: เลือก primary target type ตามลำดับความสำคัญ (phone → email → url → domain) แทนการเรียงตามตัวอักษร

## Doble-2/osint-d2

- URL: https://github.com/Doble-2/osint-d2
- Commit: `5f40bb79b6e5cab5dfa191a790ce0516b80751e0`
- วันที่ดึง: 2026-11-04
- License: MIT — ดู `LICENSE.osint-d2`
- ไฟล์:
  - `vendor/osint_d2/adapters/osint_sources/*` และ `email_sources/*`
  - `vendor/osint_d2/adapters/{profile_enricher,specific_scrapers,vector_store,rate_limiter,sherlock_runner,http_client}.py`
  - `vendor/osint_d2/services/{trust_anchor,url_guard}.py`
  - `vendor/osint_d2/core/{config,resources_loader}.py`, `core/domain/*`, `core/interfaces/*`

### สิ่งที่แก้

- เปลี่ยน import `from core.*` / `from adapters.*` เป็น absolute ภายใต้ `vendor.osint_d2.*`
- ย้าย `trust_anchor.py` และ `url_guard.py` จาก `src/core/services/` ไป `vendor/osint_d2/services/`
- เพิ่ม `__init__.py` ให้เป็น package

## สะพานเชื่อม

`vendor/_compat.py` แปลง config ของโปรเจกต์เป็น `AppSettings` ของ osint-d2 และคืน Anthropic client
เพื่อไม่ต้องแก้โค้ด vendor ให้ผูกกับผู้ให้บริการรายใดรายหนึ่ง
