# คู่มือการใช้งาน OSINT Lookup (ฉบับผู้ใช้)

> ระบบสาธิตสำหรับงานสืบสวนเบื้องต้นจากข้อมูลสาธารณะ ใช้ข้อมูลจำลอง ไม่ใช่ข้อมูลคดีจริง

## 1. สิ่งที่ต้องเตรียม

- Python 3.11 ขึ้นไป
- ติดตั้ง dependencies: `pip install -r requirements.txt`
- (ไม่บังคับ) Moli สำหรับเปิดหน้าเว็บจริง: `./scripts/install-moli.sh`
- ตั้งค่า `.env` จาก `.env.example` และใส่ `OSINT_SECRET_KEY`

## 2. เริ่มระบบ

```bash
python -m streamlit run app_modern.py        # UI
python -m uvicorn osint_agent.api.app:app --port 8000   # API
```

เปิด http://localhost:8501 แล้วเข้าสู่ระบบ

## 3. บัญชีสาธิต

| ผู้ใช้ | รหัสผ่าน | ใช้ทำอะไร |
|---|---|---|
| `admin` | `Admin#1234` | ตั้งค่า key, จัดการผู้ใช้, งานทั้งหมด |
| `analyst` | `Analyst#1234` | สืบสวนและยืนยัน candidate |
| `viewer` | `Viewer#1234` | อ่านและดาวน์โหลดรายงาน |

> เปลี่ยนรหัสผ่านก่อนใช้งานจริงโดยแก้ `config/users.json` (ค่า hash สร้างด้วย `osint_agent.auth.hash_password`)

## 4. ขั้นตอนสืบสวน

1. เลือกประเภทเป้าหมาย (เบอร์/อีเมล/ชื่อ/username/โดเมน/เลขบัญชี)
2. กรอกค่า และเลือกความลึก `quick` / `standard` / `deep`
3. กด **เริ่มสืบสวน**
4. ติดตาม Timeline ระหว่างระบบเก็บหลักฐาน
5. เปิดแท็บ **หลักฐาน** ตรวจ source และ hash
6. เปิดแท็บ **Candidates** เพื่อยืนยัน/ตัดตัวตน (analyst ขึ้นไป)
7. ดาวน์โหลดรายงาน HTML/Markdown ที่แท็บ **ส่งออก**

## 5. การอ่านผล

- **พบ** = เปิดหน้าได้และมี marker
- **ไม่พบ** = ตรวจแล้วไม่มี
- **ถูกบล็อก** = ตรวจไม่ได้ (ไม่ใช่หลักฐานว่าไม่มีบัญชี)
- ระดับความเชื่อมั่น: Confirmed / Probable / Unverified / Inferred / Speculative
- ทุกข้อควรตรวจกับหลักฐานต้นทางก่อนใช้ตัดสินใจ

## 6. API โดยย่อ

```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"analyst","password":"Analyst#1234"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -H "Authorization: Bearer $TOKEN" localhost:8000/runs
```

## 7. ปัญหาที่พบบ่อย

| อาการ | สาเหตุ | วิธีแก้ |
|---|---|---|
| 401 unauthorized | ไม่มี/หมดอายุ token | login ใหม่ |
| 403 forbidden | บทบาทไม่พอ | ใช้ analyst/admin |
| หน้าเว็บถูกบล็อก | rate limit/ต้องล็อกอิน | ดูสถานะ blocked แล้วตรวจด้วยคน |
| ไม่มีผลลัพธ์ | เป้าหมายใหม่/ข้อมูลน้อย | ลอง standard/deep หรือ pivot เพิ่ม |
| audit chain FAIL | ไฟล์ถูกแก้ | `python -m osint_agent.access` แล้วตรวจบรรทัดที่ฟ้อง |

## 8. ข้อจำกัด

- ข้อมูลสาธารณะเท่านั้น ไม่ bypass login
- ไม่เก็บเลขบัตรประชาชน/พิกัดบ้านแบบ real-time
- ผู้ใช้เป็นข้อมูลจำลอง ยังไม่เชื่อม AD/LDAP
- ระบบ bind localhost; หากเปิดสู่วงนอกให้ใช้ HTTPS และเปลี่ยนรหัสผ่าน
