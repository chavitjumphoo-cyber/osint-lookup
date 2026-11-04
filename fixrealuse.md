เห็นปัญหาหลักแล้วครับ: ตอนนี้ระบบมี เครื่องมือเยอะขึ้น แต่ยังไม่มี profiling pipeline ที่นำข้อมูลมาต่อกันจริง จึงได้ผลลัพธ์เป็น URL/identifier มากกว่าข้อมูลโปรไฟล์ที่ใช้วิเคราะห์ได้
ปัญหาปัจจุบันที่ทำให้ผลลัพธ์ไม่ดี
1. Orchestrator ใช้แผนตายตัว ไม่ได้ทำ adaptive pivot จากผลที่เพิ่งพบ
2. scan_platforms ส่วนใหญ่คืนแค่ URL และสถานะ unknown ไม่มี bio/name/location/post metadata
3. ผลจาก web_search ยังไม่ได้เปิดอ่านลิงก์สำคัญต่ออัตโนมัติ
4. Evidence extractor ดึงแค่เบอร์/อีเมล/URL/handle แต่ไม่เก็บ:
- ชื่อที่แสดง
- bio
- วันเวลาโพสต์
- บริษัท/การศึกษา
- เนื้อหาโพสต์
- ความสัมพันธ์
- ความสนใจ
5. report_builder.py สร้างรายงานเชิงสถิติ ไม่ใช่ Subject Intelligence Dossier แบบใน prompt เดิม
6. llm_polish() มีอยู่แต่ไม่ได้ถูกเรียกใน pipeline หลัก
7. system_prompt.py ฉบับใหม่ไม่ได้ถูกใช้สร้างรายงานจากข้อมูลที่เก็บจริง
8. Identity candidate สร้างจาก identifier ซ้ำเท่านั้น ยังไม่ใช้ profile metadata, avatar, bio หรือ context
9. ปัจจุบันไม่มี corpus กลางสำหรับรวมหน้าเว็บ โปรไฟล์ โพสต์ และ search result ก่อนส่งให้โมเดล
แผนดำเนินการ
Phase 0 — Push baseline ปัจจุบันก่อน
จะเตรียม commit ปัจจุบันขึ้น GitHub ก่อน โดย:
- ตรวจ git diff และ git diff --check
- ไม่ commit:
- .env
- API keys
- audit/audit.jsonl
- audit/local-before-sync-*.jsonl
- audit/runs.sqlite
- .DS_Store
- __pycache__
- เพิ่ม ignore สำหรับ runtime artifacts ที่ยังหลุดอยู่
- Stage เฉพาะ source, tests, docs, vendor และ scripts
- Commit เช่น:
feat: establish agentic OSINT foundation
- Push ไปที่:
origin/main
หลัง push จะตรวจ:
git status
git log --oneline -3
git diff origin/main
Phase 1 — สร้าง Investigation Corpus
สร้างแกนกลางใหม่:
osint_agent/profiling/
├── corpus.py
├── artifacts.py
├── leads.py
├── pivots.py
├── collectors.py
├── normalizers.py
├── entity_extractor.py
├── profile_resolver.py
├── timeline.py
├── relationships.py
└── synthesizer.py
ข้อมูลทุกชิ้นจะเก็บเป็น artifact แบบนี้:
{
  "artifact_id": "art_...",
  "source_url": "https://...",
  "source_type": "profile|search_result|post|document|api",
  "platform": "github",
  "title": "...",
  "author": "...",
  "published_at": "...",
  "retrieved_at": "...",
  "content": "...",
  "entities": [],
  "source_tool": "moli_fetch",
  "status": "ok",
  "output_hash": "sha256:...",
  "confidence": "Probable"
}
จะทำให้รายงานอ้างกลับไปยัง:
- URL จริง
- platform จริง
- search query จริง
- เวลาที่ดึงข้อมูล
- output hash
- snippet/content ที่รองรับข้อสรุป
Phase 2 — เปลี่ยนจาก Fixed Scan เป็น Lead-driven Investigation
ลูปใหม่:
Normalize target
    ↓
Generate initial search hypotheses
    ↓
Search หลายมุม
    ↓
จัดลำดับผลลัพธ์
    ↓
เปิดอ่านแหล่งสำคัญด้วย Moli
    ↓
Extract entities / names / profiles / dates
    ↓
เพิ่ม lead ใหม่เข้า queue
    ↓
ค้นต่อจาก lead ที่มีค่าที่สุด
    ↓
ตรวจความสอดคล้องและความขัดแย้ง
    ↓
สร้าง profiling dossier
แต่ละ lead จะมี:
{
  "value": "johndoe88",
  "type": "username",
  "source_artifact": "art_123",
  "reason": "พบใน bio ของ GitHub profile",
  "priority": 0.92,
  "status": "queued|running|done|rejected"
}
จะไม่ค้นซ้ำ identifier เดิมโดยไม่มีเหตุผลใหม่
Phase 3 — ปรับการสืบสวนตามประเภทเป้าหมาย
Username / บุคคล
ใช้ vendor scanner ที่มีอยู่แล้วเป็น metadata source:
- GitHub
- GitLab
- Reddit
- Telegram
- Keybase
- Twitch
- Medium
- Dev.to
- NPM
- Pinterest
- X
- Instagram
- Facebook
จากแต่ละ profile จะเก็บ:
- username
- display name
- bio
- avatar URL
- location
- company
- website
- email ที่เปิดเผย
- linked usernames
- account creation date
- follower/following ถ้ามี
- posts/repositories
- source URL
จากนั้นใช้ Moli เปิดอ่าน profile ที่สำคัญต่อ ไม่ใช้ status=200 เป็นหลักฐานเพียงอย่างเดียว
Phone
จะทำ search variants จริง:
+66812345678
66812345678
0812345678
081-234-5678
081 234 5678
ค้นหลายมุม:
"0812345678"
"0812345678" scam
"0812345678" มิจฉาชีพ
"0812345678" โกง
"0812345678" บัญชีม้า
"0812345678" site:facebook.com
"0812345678" site:pantip.com
แล้วเปิดอ่านผลลัพธ์ที่น่าสนใจเพื่อดึง:
- ชื่อ
- เพจ
- ร้านค้า
- ผู้เสียหาย
- เลขบัญชี
- เบอร์อื่น
- วันที่เกิดเหตุ
- รูปแบบการหลอกลวง
Email
จะรวม:
- HIBP
- Gravatar
- PGP
- GitHub commit/public profile
- search exact email
- username จาก local-part
- linked accounts
- domain/organization
- breach year
Domain / Phishing
จะรวม:
- Moli fetch
- DNS
- RDAP
- Wayback
- certificate/hostname
- linked domains
- contact emails
- social links
- brand impersonation
- page text/terms/contact details
Phase 4 — ทำ Profiling Dossier ตามโค้ดเดิม
รายงานใหม่จะกลับไปใช้โครงสร้างเดิมที่คุณต้องการ:
# Subject Intelligence Dossier

## 1. Identity & Digital Identifiers
## 2. Social Profiles
## 3. Associates & Relationships
## 4. Lifestyle & Interests
## 5. Geo-temporal Signals
## 6. Technical Profile
## 7. Fraud / Scam History
## 8. OpSec Exposure
## 9. Contradictions
## 10. Critical Pivot Points
## 11. Timeline
## 12. Evidence Sources
## 13. Confidence Assessment
## 14. Limitations
ข้อมูลที่จะใส่จริง
ไม่ใช่แค่:
พบ URL 5 แห่ง
แต่เป็น:
GitHub profile แสดงชื่อ "John Doe"
Bio ระบุว่าเป็น Python developer
Location ระบุ Bangkok
ลิงก์เว็บไซต์ใน bio ชี้ไปยัง example.com
ชื่อ username เดียวกันพบใน Keybase และ Telegram
ทั้งสามแหล่งใช้ avatar URL ที่มี perceptual hash ใกล้กัน
Confidence: Probable
Evidence: art_123, art_129, art_133
Phase 5 — LLM Profiling Synthesizer
เพิ่ม profiling/synthesizer.py ให้เรียก Claude/MaxPlus จริงจาก corpus ที่ผ่านการเก็บแล้ว
โมเดลจะได้รับ:
- structured artifacts
- profiles
- posts
- relations
- timeline
- contradictions
- evidence IDs
- source URLs
- confidence tier
และต้องคืน JSON schema เช่น:
{
  "executive_summary": [],
  "identity": [],
  "profiles": [],
  "associates": [],
  "interests": [],
  "timeline": [],
  "fraud_history": [],
  "technical_profile": [],
  "contradictions": [],
  "critical_pivots": [],
  "limitations": [],
  "findings": [
    {