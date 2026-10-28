"""
Tool Usage Guide - คู่มือการใช้ tools ทั้ง 15 ตัวอย่างละเอียด
สำหรับสอน AI ให้รู้จักใช้ tool ที่เหมาะสมกับสถานการณ์
"""

TOOL_USAGE_GUIDE = """
# 🛠️ TOOL USAGE GUIDE

## 📱 PHONE INVESTIGATION TOOLS

### 1. phone_info
**ใช้เมื่อ:** ได้รับเบอร์โทรศัพท์
**ผลลัพธ์:** Carrier, Country, Type (Mobile/Fixed), Timezone
**ตัวอย่าง:**
```
Input: "0812345678"
Output: Carrier: AIS, Country: TH, Type: Mobile
```
**Chain ต่อด้วย:** scan_phone_advanced → google_search

### 2. scan_phone_advanced
**ใช้เมื่อ:** ต้องการตรวจสอบ WhatsApp และหาชื่อจากเบอร์
**ผลลัพธ์:** WhatsApp status, Display name, Platform footprints
**ตัวอย่าง:**
```
Input: "0812345678"
Output: WhatsApp: Active, Name: "สมชาย ใจดี", Found on: Line, Telegram
```
**Chain ต่อด้วย:** google_search ด้วยชื่อที่เจอ → scan_platforms

---

## 👤 USERNAME INVESTIGATION TOOLS

### 3. scan_platforms
**ใช้เมื่อ:** มี username ต้องการหาว่าใช้ที่ไหนบ้าง (30+ platforms)
**ผลลัพธ์:** รายการแพลตฟอร์มที่พบ username นี้
**ตัวอย่าง:**
```
Input: "johndoe123"
Output: Found on: GitHub, Twitter, Instagram, Reddit
```
**Chain ต่อด้วย:** fetch_page (ดูโปรไฟล์) → extract_entities → google_search

### 4. sherlock_username
**ใช้เมื่อ:** scan_platforms ไม่เจอหรือต้องการค้นหาละเอียดขึ้น
**ผลลัพธ์:** รายการแพลตฟอร์มแบบละเอียด (500+ sites)
**ตัวอย่าง:**
```
Input: "johndoe123"
Output: GitHub ✓, Twitter ✓, Steam ✓, DeviantArt ✓
```
**Chain ต่อด้วย:** เหมือน scan_platforms

### 5. username_correlation
**ใช้เมื่อ:** มี username หลายตัว ต้องการหาความเชื่อมโยง
**ผลลัพธ์:** Username variants และความน่าจะเป็นที่เป็นคนเดียวกัน
**ตัวอย่าง:**
```
Input: ["johndoe", "john_doe", "jdoe123"]
Output: Correlation: 85%, Common patterns: "john", "doe"
```
**Chain ต่อด้วย:** scan_platforms กับ variants ที่เจอ

---

## 📧 EMAIL INVESTIGATION TOOLS

### 6. breach_check
**ใช้เมื่อ:** มี email ต้องการตรวจสอบข้อมูลรั่วไหล
**ผลลัพธ์:** รายการ data breaches ที่อีเมลนี้ปรากฏ
**ตัวอย่าง:**
```
Input: "john@example.com"
Output: Breached in: LinkedIn (2021), Adobe (2013), Dropbox (2012)
```
**Chain ต่อด้วย:** email_harvest → google_search

### 7. email_harvest
**ใช้เมื่อ:** มี email หนึ่งตัว ต้องการหา email related อื่นๆ
**ผลลัพธ์:** Email variants ที่เป็นไปได้
**ตัวอย่าง:**
```
Input: "john.doe@company.com"
Output: john@company.com, johndoe@gmail.com, j.doe@company.com
```
**Chain ต่อด้วย:** breach_check กับ emails ใหม่ → google_search

### 8. verify_official
**ใช้เมื่อ:** ต้องการยืนยันว่า email/domain เป็นของหน่วยงานจริง
**ผลลัพธ์:** Verification status
**ตัวอย่าง:**
```
Input: email="john@google.com", claimed_entity="Google Inc"
Output: Verified ✓ (MX records match)
```

---

## 🔍 WEB SEARCH & SCRAPING TOOLS

### 9. google_search
**ใช้เมื่อ:** ต้องการค้นหาข้อมูลใดๆ บน Google
**ผลลัพธ์:** Search results พร้อม snippets
**ตัวอย่าง:**
```
Input: '"0812345678" site:facebook.com'
Output: [Facebook profiles containing phone number]
```
**Tips:**
- ใช้ site: เพื่อค้นเฉพาะเว็บ
- ใช้ "" เพื่อค้นคำที่ตรงทุกอักษระ
- ใช้ OR เพื่อค้นหลายคำ
**Chain ต่อด้วย:** fetch_page (URL ที่เจอ) → extract_entities

### 10. fetch_page
**ใช้เมื่อ:** มี URL ต้องการดึงเนื้อหาหน้าเว็บ
**ผลลัพธ์:** HTML content, screenshots (ถ้ามี)
**ตัวอย่าง:**
```
Input: "https://github.com/johndoe"
Output: [Page content with bio, repos, followers]
```
**Chain ต่อด้วย:** extract_entities

### 11. extract_entities
**ใช้เมื่อ:** มีเนื้อหาข้อความ ต้องการดึง email, phone, names
**ผลลัพธ์:** รายการ entities ที่เจอ
**ตัวอย่าง:**
```
Input: "Contact John at john@email.com or 081-234-5678"
Output: Emails: [john@email.com], Phones: [0812345678], Names: [John]
```
**Chain ต่อด้วย:** breach_check (email) / phone_info (phone) / google_search (name)

---

## 🧠 ADVANCED ANALYSIS TOOLS

### 12. compare_avatars
**ใช้เมื่อ:** มีรูป avatar 2 รูป ต้องการเปรียบเทียบว่าเป็นคนเดียวกันไหม
**ผลลัพธ์:** Similarity score (perceptual hash)
**ตัวอย่าง:**
```
Input: url1="https://avatar1.jpg", url2="https://avatar2.jpg"
Output: Similarity: 92% (Likely same person)
```

### 13. correlate_stylometry
**ใช้เมื่อ:** มีข้อความ 2 ชุด ต้องการเปรียบเทียบรูปแบบการเขียน
**ผลลัพธ์:** Writing style similarity
**ตัวอย่าง:**
```
Input: text1="Hello world...", text2="Hi there..."
Output: Similarity: 78% (Similar writing style)
```

### 14. identity_candidate
**ใช้เมื่อ:** มีข้อมูลจากหลายแหล่ง ต้องการวิเคราะห์ว่าเป็นคนเดียวกัน
**ผลลัพธ์:** Identity confidence score และ evidence
**ตัวอย่าง:**
```
Input: profiles=[{platform: "GitHub", name: "John"}, {platform: "Twitter", name: "John Doe"}]
Output: Confidence: 85%, Evidence: Same name, Similar bio, Location match
```

### 15. darkweb_monitor
**ใช้เมื่อ:** ต้องการค้นหาข้อมูลรั่วไหลใน darkweb (scaffold)
**ผลลัพธ์:** Leaked data findings
**หมายเหตุ:** ยังเป็น placeholder ยังไม่มีการเชื่อมต่อจริง

---

# 🎯 INVESTIGATION WORKFLOWS

## Workflow 1: Phone Number Investigation
```
1. phone_info(phone) → รู้ carrier
2. scan_phone_advanced(phone) → เจอชื่อ "สมชาย"
3. google_search('"สมชาย" "0812345678"') → เจอ Facebook
4. fetch_page(facebook_url) → ดึงข้อมูลโปรไฟล์
5. extract_entities(page_content) → เจอ email, username
6. breach_check(email) → ตรวจสอบ breach
7. scan_platforms(username) → หาแพลตฟอร์มอื่น
```

## Workflow 2: Username Investigation
```
1. scan_platforms(username) → เจอ GitHub, Twitter, Instagram
2. fetch_page(github_url) → ดึงโปรไฟล์ GitHub
3. extract_entities(content) → เจอ email "john@email.com"
4. breach_check(email) → ตรวจสอบ breach
5. email_harvest(email) → หา email variants
6. google_search('"john@email.com"') → หาข้อมูลเพิ่ม
7. sherlock_username(username) → ค้นหาแพลตฟอร์มเพิ่ม
```

## Workflow 3: Email Investigation
```
1. breach_check(email) → เจอใน LinkedIn breach
2. email_harvest(email) → หา variants
3. google_search('"email@domain.com"') → หาโปรไฟล์
4. fetch_page(results) → ดึงข้อมูล
5. extract_entities(content) → เจอ username
6. scan_platforms(username) → หาแพลตฟอร์ม
```

## Workflow 4: Name Investigation
```
1. google_search('"John Doe" site:linkedin.com') → หา LinkedIn
2. google_search('"John Doe" site:facebook.com') → หา Facebook
3. fetch_page(linkedin_url) → ดึงข้อมูล
4. extract_entities(content) → เจอ email, phone
5. breach_check(email) → ตรวจสอบ
6. phone_info(phone) → ตรวจสอบเบอร์
```

---

# ⚠️ IMPORTANT RULES

## ✅ DO:
- เริ่มด้วย tool ที่ตรงที่สุดกับ input type
- Chain tools ทันทีเมื่อได้ข้อมูลใหม่
- ใช้ google_search บ่อยๆ กับข้อมูลใหม่
- Extract entities จากทุกหน้าเว็บที่ดึงมา
- เก็บหลักฐานและบันทึกแหล่งที่มา

## ❌ DON'T:
- อย่า google_search คำเดิมซ้ำ
- อย่า scan_platforms username เดิมซ้ำ
- อย่าใช้ tool ที่ได้ผลซ้ำๆ
- อย่าลืม chain tools ต่อเมื่อได้ข้อมูลใหม่
- อย่าหยุดเร็วเกินไป ถ้ายังมี lead ให้ตาม

## 🎯 WHEN TO STOP:
- ได้ข้อมูลครบถ้วนแล้ว (ชื่อ, contact, platforms)
- ผลลัพธ์เริ่มซ้ำซาก
- ใช้ tools ครบทุกตัวที่เกี่ยวข้องแล้ว
- ไม่มี lead ใหม่ให้ตามแล้ว

---

# 💡 PRO TIPS

1. **Always extract entities** - ทุกครั้งที่ได้ข้อมูลใหม่ ให้ extract entities ออกมา
2. **Google is your friend** - ใช้ Google Search กับทุกข้อมูลใหม่ (ชื่อ, email, username, phone)
3. **Chain intelligently** - คิดว่าข้อมูลที่ได้สามารถนำไปใช้กับ tool ไหนต่อ
4. **Use site: operator** - ค้นเฉพาะเว็บที่ต้องการ (facebook.com, linkedin.com, twitter.com)
5. **Verify everything** - ใช้หลายแหล่งยืนยันข้อมูลเดียวกัน

---

เลือก tool ที่เหมาะสมและ chain ต่อจากผลลัพธ์!
"""
