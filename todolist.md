# Todo — คืนความสามารถ Agentic AI OSINT อย่างมีหลักฐาน

> บริบท: เวอร์ชันแรกดูวิเคราะห์เก่งกว่าเพราะ LLM เป็นคนคิดและเลือก pivot เอง ส่วนเวอร์ชันปัจจุบันใช้ orchestrator ตายตัว ถึงเครื่องมือจะเยอะขึ้นแต่ "สมองที่ตัดสินใจ" ถูกถอดออกจากเส้นทางใช้งานจริง
>
> เป้าหมาย: ให้ LLM เป็น planner จริง แต่ deterministic evidence core คุมความจริงของข้อมูล ห้าม LLM แต่ง evidence เอง

## กติกากลาง

- [ ] LLM เลือก action ได้ แต่ทุก action ต้องผ่าน Evidence Core
- [ ] ทุกผล tool ต้องกลายเป็น artifact ที่มี `source_url`, `source_type`, `output_hash`, `retrieved_at`
- [ ] LLM ห้ามสร้าง identifier หรือผล tool เอง
- [ ] ทุก finding ต้องอ้าง `artifact_id` ที่มีจริง
- [ ] มี budget คุม step/fetch/time และหยุดเมื่อ information gain ต่ำ
- [ ] ไม่มี API key → deterministic fallback และต้องแจ้งผู้ใช้ว่าไม่ใช่ agentic เต็มรูปแบบ

---

## 1. Agent Engine v2 — เสร็จแล้ว

- [ ] สร้าง `osint_agent/services/agent_engine.py`
- [ ] สร้าง `osint_agent/services/agent_state.py`
- [ ] สร้าง `osint_agent/services/agent_tools.py`
- [ ] สร้าง `osint_agent/services/agent_prompts.py`
- [ ] AgentState เก็บ `target`, `target_type`, `objective`, `artifacts`, `profiles`, `entities`, `leads`, `pivots_completed`, `contradictions`, `six_d_profile`, `budget`
- [ ] ทุก action เขียน event `agent_action` พร้อม `action`, `target`, `reason`, `expected_value`, `evidence_before`
- [ ] Planner เลือก: search / scan / fetch / extract / pivot / finalize
- [ ] บังคับ `finalize_report` เมื่อ budget หมด
- [ ] ใช้เฉพาะ standard/deep; quick ใช้ deterministic

## 2. Tool surface สำหรับ agent — เสร็จแล้ว

- [ ] จัดกลุ่ม tool ให้ LLM เลือกง่าย:
  - [ ] `search_web`
  - [ ] `scan_profiles`
  - [ ] `fetch_profile`
  - [ ] `fetch_page`
  - [ ] `extract_profile`
  - [ ] `extract_entities`
  - [ ] `scan_github`
  - [ ] `scan_email`
  - [ ] `scan_phone`
  - [ ] `compare_avatar`
  - [ ] `compare_profiles`
  - [ ] `search_corpus`
  - [ ] `add_lead`
  - [ ] `verify_identity_candidate`
  - [ ] `finalize_report`
- [ ] ไม่ expose low-level tool ทั้งหมดโดยไม่จัดกลุ่ม
- [ ] tool ทุกตัวคืน structured result ไม่ใช่ string ลอย

## 3. Profile Extractor — เสร็จแล้ว

- [ ] สร้าง `osint_agent/profiling/profile_extractor.py`
- [ ] เรียกอัตโนมัติทุกครั้งที่ fetch สำเร็จ
- [ ] สกัด: display_names, aliases, usernames, bio, locations, organizations, education, websites, emails, phones, avatar_urls, account_created_at, followers, following, repositories, posts, languages, interests, published_dates, relations
- [ ] ทุก field มี `value`, `source_artifact`, `source_url`, `snippet`, `confidence`
- [ ] ใช้ LLM extract แบบ JSON schema ต่อหน้าเมื่อมี key
- [ ] regex fallback เมื่อไม่มี key

## 4. Moli เป็น agent browser — เสร็จแล้ว

- [ ] เพิ่ม tool ระดับสูง: `browser_observe`, `browser_extract`, `browser_follow_links`, `browser_capture_profile`
- [ ] Agent ไม่ต้องรู้ DOM selector เอง
- [ ] `browser_capture_profile` คืน title/bio/location/company/avatar/links/repos/artifact_id
- [ ] คุมด้วย budget และ block private network

## 5. Identity Resolution จาก metadata — เสร็จแล้ว

- [ ] เพิ่ม ownership score:
  - [ ] email ตรง 1.00
  - [ ] phone ตรง 1.00
  - [ ] explicit link 0.95
  - [ ] source-native ID 0.95
  - [ ] avatar hash 0.80
  - [ ] full name 0.55
  - [ ] bio similarity 0.45
  - [ ] org/location 0.35
  - [ ] username ซ้ำ 0.15
  - [ ] interest 0.10
- [ ] ผลลัพธ์เป็น Confirmed / Probable / Possible / Contradicted / Unverified
- [ ] ห้ามสรุปว่าเป็นคนเดียวกันจาก username ซ้ำ
- [ ] ต้องมี human review ก่อนยืนยัน

## 6. 6D Cognitive Profiling — เสร็จแล้ว

- [ ] Identity: display name, aliases, cross-link, avatar, bio, email/phone, account age, cross-platform consistency
- [ ] Geo-temporal: public location, timezone, post timestamp, check-in, profile dates
- [ ] Psychological/OCEAN: ต้องมีข้อความ 3–5 ชิ้นต่างแหล่ง; รายงานเป็น Speculative
- [ ] Technical: repos, languages, packages, commits, technical posts
- [ ] Ideological: ต้องมีข้อความแสดงจุดยืนชัดเจนหลายชิ้น ไม่สรุปจาก follow/like
- [ ] OpSec: email/phone/location ที่เผยแพร่, avatar reuse, linked account, metadata
- [ ] ทุกมิติระบุ "ประเมินไม่ได้" เมื่อหลักฐานไม่พอ

## 7. รายงาน — เสร็จแล้ว

- [ ] Dossier 15 หัวข้อตาม template เดิม
- [ ] 6D เป็นหัวข้อ 8 พร้อมหัวข้อย่อย 8.1–8.6
- [ ] แยก Research Report ตาม `Write Template.docx`
- [ ] Research Report ไม่ปนข้อมูล target
- [ ] ทุก finding มี evidence id + URL + confidence
- [ ] Limitations บังคับทุกฉบับ

## 8. เส้นทางใช้งาน — เสร็จแล้ว

- [ ] Streamlit/API → AgentEngine
- [ ] AgentEngine → AgentState → LLM Planner → EvidenceCore → Corpus → ProfileExtractor → LeadQueue → CognitiveProfiler → DossierSynthesizer
- [ ] Quick = deterministic scan + fetch จำกัด
- [ ] Standard = LLM agent + corpus + extraction
- [ ] Deep = LLM agent + ทุก pivot + probe + 6D + cross-check
- [ ] ไม่มี key → fallback + แจ้งเหตุ

## 9. Test และเกณฑ์รับงาน

- [ ] unit test AgentState, budget, action log
- [ ] test profile extractor จาก fixture HTML
- [ ] test ownership scoring (คู่จริง/คู่ namesake)
- [ ] test 6D insufficient-data
- [ ] test LLM finding ที่อ้าง evidence ปลอมต้องถูกตัด
- [ ] integration test ด้วย fake LLM
- [ ] ทดลองจริง username / เบอร์ / email / domain ชนิดละกรณี
- [ ] วัดเปิดหน้าสำเร็จ, ฟิลด์ที่สกัดได้, pivots ที่เพิ่มข้อมูลใหม่, เวลา, ค่าใช้จ่าย, false match, จำนวน finding ที่มนุษย์แก้
- [ ] `pytest` เขียว, `ruff` clean

## 10. ลำดับลงมือ

1. [ ] AgentState + AgentEngine + action log
2. [ ] Profile Extractor + browser_capture_profile
3. [ ] Ownership scoring
4. [ ] ต่อ AgentEngine เข้า Streamlit/API
5. [ ] 6D จากข้อมูลที่สกัดจริง
6. [ ] Dossier + Research Report
7. [ ] Test และทดลองจริง

## Definition of Done

- [ ] standard/deep เรียก LLM planner จริงเมื่อมี key
- [ ] ทุก finding ย้อนกลับถึง artifact ได้
- [ ] profile fields มาจากหน้าเว็บจริง ไม่ใช่แค่ username
- [ ] 6D แสดงครบและไม่ overclaim
- [ ] ไม่มี regression ของหลักฐาน/hash/limitations
- [ ] ผ่าน test, lint และทดลองจริงครบ 4 ชนิด target


เวอร์ชันหลังมีเครื่องมือมากขึ้น แต่ความสามารถเชิงวิเคราะห์ลดลง เพราะเราเปลี่ยนเส้นทางการทำงานจาก LLM ที่คิดและเลือกเครื่องมือเอง ไปเป็น orchestrator แบบกำหนดขั้นตายตัว
สาเหตุหลักที่เวอร์ชันแรกดูวิเคราะห์ดีกว่า
เวอร์ชันแรก
เส้นทางจริงคือ:
Streamlit
  → run_osint_lookup()
  → Claude ReAct loop
  → Claude เลือกเครื่องมือเอง
  → อ่านผลรอบก่อน
  → คิด pivot ใหม่
  → fetch หน้าเว็บ
  → extract entities
  → ค้นต่อ
  → Claude สังเคราะห์รายงาน
จุดสำคัญคือ Claude ได้เห็น ประวัติทั้งหมดใน conversation และสามารถตัดสินใจต่อเอง เช่น:
ค้น username
→ พบ GitHub
→ เปิด GitHub
→ เจอชื่อจริง/เว็บไซต์
→ ค้นชื่อจริง
→ เจอ Reddit
→ เปิด Reddit
→ เจออีเมล/องค์กร
→ ค้นอีเมลต่อ
→ สรุป profile
แม้โค้ดเก่าจะมีปัญหา IdentityTriangulator ที่สร้างแต่ไม่ได้ใช้จริง แต่ความรู้สึกว่า “วิเคราะห์ได้ดี” มาจาก LLM ReAct + system prompt เดิมที่มี Dossier/6D/pivot instructions ไม่ใช่จาก triangulator
เวอร์ชันปัจจุบัน
เส้นทางจริงคือ:
Streamlit
  → Orchestrator
  → queries ที่กำหนดไว้ล่วงหน้า
  → scan
  → fetch ตามจำนวนจำกัด
  → resolver แบบ deterministic
  → report builder
ปัญหาคือ:
agent.py ที่มี ReAct loop ไม่ได้ถูกเรียกจาก UI/API แล้ว
system_prompt.py ไม่ได้ถูกส่งเข้าไปตอนสร้าง dossier deterministic
llm_synthesize() เป็นแค่การเรียกครั้งสุดท้าย ไม่ได้ช่วยวางแผนการค้น
extract_with_llm() มีอยู่แต่ไม่ได้ถูกเรียกกับแต่ละ profile/page
profile resolver รวมข้อมูลจากชื่อ/username แต่ยังไม่วิเคราะห์ ownership อย่างลึก
search result ถูกเก็บเป็น artifact แต่การตัดสินใจ pivot ยังไม่ได้ให้โมเดลเลือก
deep ตอนนี้คือ “จำนวนรอบมากขึ้น” ไม่ใช่ “agent ฉลาดขึ้น”
รายงานดีขึ้นในเชิงโครงสร้าง แต่ยังไม่ใช่การวิเคราะห์เชิงเหตุผลเต็มรูปแบบ
สรุปสั้น ๆ:
เราเพิ่มระบบ evidence และ safety guardrail สำเร็จ แต่เผลอถอด “สมองที่ตัดสินใจ” ออกจากเส้นทางใช้งานจริง
แบบที่ควรทำ: Dual-Agentic Architecture
ไม่ควรย้อนกลับไปใช้ ReAct รุ่นเก่าแบบไม่มีหลักฐาน เพราะจะกลับไปเจอปัญหา hallucination และเก็บข้อมูลมั่ว
ควรใช้สองชั้นพร้อมกัน:
LLM Agent Brain
  ├── วางแผน
  ├── เลือก tool
  ├── อ่านผล
  ├── สร้าง lead
  ├── เลือก pivot
  └── ตัดสินใจหยุด

Deterministic Evidence Core
  ├── ตรวจ URL
  ├── รัน tool
  ├── hash output
  ├── เก็บ artifact
  ├── กัน duplicate
  ├── คุม budget
  ├── ตรวจ source
  └── ห้าม LLM สร้างหลักฐานเอง
LLM จะเป็นผู้วางแผนและวิเคราะห์ แต่ Evidence Core เป็นผู้ควบคุมความจริงของข้อมูล
สถาปัตยกรรมใหม่ที่แนะนำ
1. Agent Engine ใหม่
สร้าง:
osint_agent/services/agent_engine.py
osint_agent/services/agent_state.py
osint_agent/services/agent_tools.py
osint_agent/services/agent_prompts.py
Agent State
สถานะที่ LLM ต้องเห็นทุกครั้ง:
{
  "target": "johndoe",
  "target_type": "username",
  "objective": "สร้าง Subject Intelligence Dossier",
  "artifacts": [],
  "profiles": [],
  "entities": [],
  "leads": [],
  "pivots_completed": [],
  "contradictions": [],
  "six_d_profile": {},
  "budget": {
    "steps_used": 4,
    "max_steps": 30,
    "fetches_used": 6,
    "max_fetches": 20
  }
}
เครื่องมือที่ agent ควรเลือกเอง
search_web
scan_profiles
fetch_profile
fetch_page
extract_profile
extract_entities
scan_github
scan_email
scan_phone
compare_avatar
compare_profiles
search_corpus
add_lead
verify_identity_candidate
finalize_report
ไม่ควร expose เครื่องมือ low-level ทั้งหมดให้โมเดลโดยไม่มีการจัดกลุ่ม เพราะจะทำให้โมเดลเลือก tool ผิดหรือวนซ้ำ
2. ลูป Agentic จริง
1. Normalize target
2. สร้าง initial hypotheses
3. Agent เลือก search query แรก
4. Search
5. Agent อ่านผลลัพธ์
6. เลือก URL สำคัญ
7. Fetch ด้วย Moli
8. Extract profile metadata
9. เพิ่ม entity/lead ใหม่
10. Agent เลือก pivot ที่มี information gain สูงสุด
11. ตรวจซ้ำกับแหล่งอื่น
12. วิเคราะห์ contradiction
13. สร้าง/อัปเดต 6D profile
14. Agent ตัดสินใจ:
    - ค้นต่อ
    - เปิดหน้าเพิ่ม
    - ยืนยัน candidate
    - หยุดและสรุป
ทุกครั้งที่ agent เลือก action ต้องบันทึกเป็น event:
{
  "kind": "agent_action",
  "action": "fetch_profile",
  "target": "https://github.com/johndoe",
  "reason": "ผลค้นพบ URL โปรไฟล์ GitHub และมีคะแนน relevance สูง",
  "expected_value": "ชื่อ, bio, location, organization, avatar",
  "evidence_before": ["art_123"]
}
แสดง rationale แบบนี้ให้ผู้ใช้เห็นได้ แต่ไม่ต้องแสดง private chain-of-thought
3. Profile Extractor ต้องทำงานทุกหน้า
ปัจจุบัน extractor ส่วนใหญ่ทำงานตอนท้ายหรือใช้ regex เท่านั้น ควรเพิ่ม:
osint_agent/profiling/profile_extractor.py
ทุกครั้งที่ fetch_page หรือ fetch_profile สำเร็จ ให้สกัด:
{
  "display_names": [],
  "aliases": [],
  "usernames": [],
  "bio": "",
  "locations": [],
  "organizations": [],
  "education": [],
  "websites": [],
  "emails": [],
  "phones": [],
  "avatar_urls": [],
  "account_created_at": "",
  "followers": null,
  "following": null,
  "repositories": [],
  "posts": [],
  "languages": [],
  "interests": [],
  "published_dates": [],
  "relations": []
}
แต่ละ field ต้องมี:
{
  "value": "John Doe",
  "source_artifact": "art_123",
  "source_url": "https://github.com/johndoe",
  "snippet": "John Doe · Python developer",
  "confidence": "Probable"
}
ถ้ามี Claude/MaxPlus ให้เรียก LLM extract แบบ JSON schema ต่อหน้า ไม่ควรส่งแต่ corpus รวมยาว ๆ ตอนท้ายทีเดียว
4. Identity Resolution ต้องใช้ metadata ไม่ใช่ username ซ้ำอย่างเดียว
คะแนน ownership ควรแบ่งเป็น:
สัญญาณ	น้ำหนัก
อีเมลตรงกัน	1.00
เบอร์ตรงกัน	1.00
explicit link จากเจ้าของบัญชี	0.95
source-native ID ตรงกัน	0.95
avatar perceptual hash	0.80
ชื่อเต็มตรงกัน	0.55
bio similarity	0.45
organization/location ตรงกัน	0.35
username ซ้ำ	0.15
interest คล้าย	0.10
ผลลัพธ์ต้องเป็น:
Confirmed
Probable
Possible
Contradicted
Unverified
ห้าม:
username = johndoe เหมือนกัน
→ เป็นคนเดียวกัน
ต้องได้:
GitHub johndoe และ Telegram johndoe
- username ตรง
- display name ตรง
- avatar hash ใกล้กัน
- bio มีลิงก์ไปเว็บไซต์เดียวกัน
- location ตรง

ผล: Probable
5. 6D Cognitive Profiling ต้องใช้ข้อมูลที่เหมาะกับแต่ละมิติ
Identity
ใช้:
display name
aliases
usernames
linked accounts
avatar
bio
email/phone
account age
cross-platform consistency
Geo-temporal
ใช้:
public location ที่เจ้าตัวระบุ
timezone จาก profile/API
timestamp ของโพสต์
public check-in
วันที่เริ่ม/แก้ไข profile
ช่วงเวลาที่โพสต์
ห้ามสรุปจากโพสต์เดียวว่า “อยู่ที่ไหน” หรือ “ใช้ชีวิตเวลาใด”
Psychological / OCEAN
ต้องมีข้อความอย่างน้อย 3–5 ชิ้นจากแหล่งที่ต่างกันก่อนวิเคราะห์
วิเคราะห์ได้เพียง:
รูปแบบการเขียน
ความยาวข้อความ
การใช้คำถาม/อุทาน
first-person language
emoji
หัวข้อที่วนซ้ำ
รูปแบบการตอบโต้
ผลต้องเป็น:
Speculative — มีสัญญาณที่อาจสอดคล้องกับ Extraversion สูง
เหตุผล: มีข้อความสาธารณะ 12 ชิ้น, มีการตอบโต้ต่อเนื่อง 8 ชิ้น
ไม่ควรเขียน:
บุคคลนี้เป็นคน extrovert
Technical
ใช้:
GitHub repositories
languages
npm packages
commit history
Stack Overflow
bio
job postings
technical posts
Ideological
ต้องมีข้อความที่เจ้าตัวแสดงจุดยืนชัดเจนหลายชิ้น ไม่ใช่สรุปจาก:
follow
like
เพื่อน
platform ที่เข้าร่วม
keyword เดียว
OpSec
ใช้:
อีเมลที่เผยแพร่
เบอร์ที่เผยแพร่
location ที่เผยแพร่
reuse ของ avatar
linked accounts
metadata
domain/website exposure
6. ปรับ report ให้ตรงกับ Template เดิม
รายงานหลักควรเป็น:
Subject Intelligence Dossier

1. Executive Summary
2. Identity & Digital Identifiers
3. Social Profiles
4. Associates & Relationships
5. Lifestyle & Interests
6. Geo-temporal Signals
7. Technical Profile
8. 6D Cognitive Profiling
   8.1 Identity
   8.2 Geo-temporal
   8.3 Psychological/OCEAN
   8.4 Technical
   8.5 Ideological
   8.6 OpSec
9. Fraud / Scam History
10. Contradictions
11. Critical Pivot Points
12. Timeline
13. Evidence Sources
14. Confidence Assessment
15. Limitations
และแยกอีกรายงาน:
Research Report ตาม Write Template.docx
รายงานวิจัยใช้สำหรับอธิบายระบบ/การทดลอง ไม่ใช่เอาไปปนกับ profile ของ target
7. ทำให้ Moli ใช้เป็น agent browser จริง
ตอนนี้ Moli ถูกใช้เป็น fetch backend แต่ยังไม่ได้เป็นส่วนหนึ่งของ agent decision loop
ควรเพิ่ม tool ระดับสูง:
browser_observe(url)
browser_extract(selector_or_goal)
browser_follow_links(url, max_links)
browser_capture_profile(url)
Agent ไม่ควรต้องรู้ DOM selector เองทั้งหมด
ตัวอย่าง:
{
  "tool": "browser_capture_profile",
  "input": {
    "url": "https://github.com/johndoe",
    "goal": "extract public identity and technical profile"
  }
}
ผลลัพธ์:
{
  "title": "John Doe",
  "bio": "Python developer",
  "location": "Bangkok",
  "company": "Acme",
  "avatar_url": "...",
  "repositories": [],
  "linked_urls": [],
  "artifact_id": "art_..."
}
8. เส้นทางการใช้งานที่ควรเปลี่ยน
ปัจจุบัน:
Streamlit → Orchestrator แบบ deterministic
ควรเป็น:
Streamlit/API
  → AgentEngine
      → AgentState
      → LLM Planner
      → EvidenceCore
      → Corpus
      → ProfileExtractor
      → LeadQueue
      → CognitiveProfiler
      → DossierSynthesizer
เลือกโหมดดังนี้:
Mode	การทำงาน
Quick	deterministic scan + จำกัด fetch
Standard	LLM agent + corpus + profile extraction
Deep	LLM agent + ทุก pivot + platform probe + 6D + cross-check
Standard/Deep ต้องเรียก AgentEngine จริง เมื่อมี Anthropic/MaxPlus key
ถ้าไม่มี key ให้ใช้ deterministic fallback แต่ต้องแจ้งผู้ใช้ว่าเป็น fallback ไม่ใช่ Agentic AI เต็มรูปแบบ
สรุปการวินิจฉัย
เวอร์ชันแรกดูดีกว่าเพราะ:
Claude เป็นคนคิดว่าจะทำอะไรต่อ
เวอร์ชันปัจจุบันด้อยลงเพราะ:
โค้ดเป็นคนกำหนดว่าจะทำอะไรต่อ
วิธีแก้ไม่ใช่เพิ่มเครื่องมืออีก แต่ต้อง:
นำ LLM ReAct กลับมาเป็น planner จริง
ให้ planner เห็น corpus/lead/profile/evidence state
ให้ทุก tool result กลายเป็น structured artifact
เรียก profile extractor ต่อหน้าเว็บทันที
ให้ lead queue ผลิต pivot ใหม่
ให้ identity resolver ใช้ metadata
ให้ 6D profiler วิเคราะห์จากข้อความ/โปรไฟล์ที่เพียงพอ
ให้ report อ้าง evidence ทุกข้อ
ใช้ deterministic core คุมไม่ให้ LLM แต่งข้อมูล
แนะนำให้เริ่มจาก AgentEngine v2 + AgentState + profile extractor ก่อน เพราะเป็นจุดที่ทำให้ระบบกลับมาเป็น Agentic AI จริงที่สุด.