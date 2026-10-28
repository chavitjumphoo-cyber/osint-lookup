# OSINT Lookup - Modern UI

## 🎨 วิธีใช้ Modern UI

### Option 1: Streamlit Modern UI (ใช้งานได้ทันที)

```bash
# รัน modern version ที่ port 8502
streamlit run app_modern.py --server.port 8502
```

แล้วเปิด: `http://localhost:8502`

**Features:**
- ✅ shadcn-ui inspired design
- ✅ Smooth animations (fade, slide, pulse)
- ✅ Modern cards & badges
- ✅ Timeline with icons
- ✅ Gold accent theme
- ✅ ใช้ระบบ OSINT เดิมได้เต็มรูปแบบ

---

### Option 2: FastAPI + Next.js (Full Stack)

**Backend (FastAPI):**
```bash
# Install dependencies
pip install fastapi uvicorn websockets

# Run backend API
python backend_api.py
```

Backend จะรันที่: `http://localhost:8000`

**Frontend (Next.js):**
```bash
cd frontend
npm install
npm run dev
```

Frontend จะรันที่: `http://localhost:3000`

---

### Option 3: HTML Mockup (Static Demo)

เปิดไฟล์โดยตรง:
```bash
start mockup.html
```

---

## 📁 ไฟล์ที่สร้างขึ้น

1. **app_modern.py** - Streamlit version พร้อม modern UI
2. **backend_api.py** - FastAPI REST API + WebSocket
3. **mockup.html** - Static HTML mockup พร้อม animations
4. **frontend/** - Next.js app (ถ้า option 2)

---

## 🎯 แนะนำ: ใช้ app_modern.py

เพราะ:
- ✅ ใช้งานได้ทันทีโดยไม่ต้อง setup เพิ่ม
- ✅ เชื่อมต่อกับ osint_agent เดิมทั้งหมด
- ✅ Modern UI พร้อม animations
- ✅ รองรับ Thai language เต็มรูปแบบ

---

## 🔄 เปรียบเทียบ

| Feature | app.py (เดิม) | app_modern.py | FastAPI+Next.js |
|---------|---------------|---------------|-----------------|
| Modern UI | ❌ | ✅ | ✅ |
| Animations | ❌ | ✅ | ✅ |
| Setup Time | 0 min | 0 min | 15 min |
| Real-time | ✅ | ✅ | ✅ |
| WebSocket | ❌ | ❌ | ✅ |
| Mobile | ⚠️ | ⚠️ | ✅ |

---

## 💡 Quick Start

```bash
# ปิด Streamlit เดิม (Ctrl+C)
# รัน modern version
streamlit run app_modern.py --server.port 8502
```

จากนั้นเปิด browser ไปที่: `http://localhost:8502`
