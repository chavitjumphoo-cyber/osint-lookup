# Threat model (ย่อ)

## สินทรัพย์
- หลักฐานและ hash ใน `audit/runs.sqlite`
- API key ใน `.env`
- ตัวตนของเป้าหมายและของผู้ใช้งานเอง

## ภัยคุกคาม

| ภัย | มาตรการ |
|---|---|
| SSRF ผ่าน URL ที่เป้าหมายให้มา | `tools/http.py` ตรวจก่อน + Moli `--block-private-networks` + `url_guard` ตอน fallback |
| Prompt injection จากหน้าเว็บ | wrap `<untrusted_data>` + escape closing tag |
| ข้อมูลถูกแต่งในรายงาน | `output_hash` sha256 + `verify_output_integrity` |
| Moli subprocess ถูกยัด argument | เรียกด้วย arg list ไม่ผ่าน shell, timeout, จำกัดขนาดผล |
| โดน rate limit / บล็อก IP | `DomainRateLimiter`, per-host budget, รายงานสถานะ `blocked` |
| อ่าน run ของคนอื่นบนเครื่องเดียว | bind localhost + login/RBAC (viewer/analyst/admin) — ถ้าเปิดวงนอกต้องใช้ HTTPS |
| เดารหัสผ่าน / token ถูกขโมย | PBKDF2-SHA256, lock 5 ครั้ง/5 นาที, token HMAC อายุ 8 ชม., audit login ทุกครั้ง |
| API key รั่วใน log | ไม่ log key, อ่านจาก `.env` เท่านั้น |
| checkpoint ถูกแก้ | hash-chain ใน `access.py` + export ตรวจได้ |

## ข้อจำกัดที่ทราบ
- ผู้ใช้เป็นข้อมูลจำลอง (demo) ยังไม่มี integration กับ AD/LDAP
- `search_evidence`/report เป็นข้อความที่ยังต้องตรวจด้วยคน
- trust anchor เป็น heuristic — anchor ผิดทำให้ recall ต่ำ
