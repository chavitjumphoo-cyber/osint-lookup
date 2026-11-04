# Anti-hallucination rules (ยกมาจากแนวทาง osint-agent-skills)

## กติกาการใช้ confidence

ใช้คำศัพท์ 5 ระดับเท่านั้น: Confirmed / Probable / Unverified / Inferred / Speculative
ห้ามใช้คำกำกวม เช่น "น่าจะ", "อาจจะ" โดยไม่ติดป้าย

## Rule 1 — ห้ามแต่ง identifier

ถ้าไม่ได้เห็นในผล tool หรือแหล่งที่อ้าง ห้ามใส่เบอร์ อีเมล username IP วันที่ ชื่อเหตุการณ์

## Rule 2 — ห้ามแต่งผล tool

ถ้าไม่ได้รัน tool ห้ามบรรยายผลของมัน ถ้าถูกถามให้บอกว่า "ยังไม่ได้รัน"

## Rule 3 — แยก observed ออกจาก inferred

ข้อความที่อนุมานต้องมีคำว่า Inferred และแสดงเหตุผล ข้อความ Speculative ต้องอยู่นอกหัวข้อ findings

## Rule 4 — cite or retract

ทุกประโยคข้อเท็จจริงต้องมี source ถ้าใส่ source ไม่ได้ ให้ลบประโยคนั้น

## Rule 5 — แยก tool-failure จาก empty-result

- `failed` / `blocked` → "ตรวจไม่ได้"
- `empty` → "ตรวจแล้วไม่พบ"

## Rule 6 — เปิดเผยความสดของข้อมูล

ข้อมูล OSINT เน่าเร็ว ระบุวันที่เข้าถึง และเตือนให้ตรวจซ้ำเมื่ออ้างข้อมูลที่อาจเปลี่ยน

## Rule 7 — face/avatar match เป็น Probable

ผล perceptual hash หรือ face matching เป็น Probable จนกว่าจะมีหลักฐาน corroborate

## Rule 8 — output integrity

ทุกผล tool มี `output_hash` (sha256) ใช้ `verify_output_integrity` ตรวจได้
