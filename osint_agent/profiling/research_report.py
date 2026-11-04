"""รายงานวิจัยตามโครงร่าง DOCX จากข้อมูล run จริง (ไม่เติมตัวเลขที่ไม่มี)"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from . import cognitive


def _stats(run: dict, artifacts: list[dict], findings: list[dict], profiles: list[dict]) -> dict:
    by_type = Counter(a.get("source_type") for a in artifacts)
    statuses = Counter(f.get("status") for f in findings)
    opened = sum(1 for a in artifacts if a.get("source_type") in {"profile", "post", "page"} and a.get("content"))
    return {
        "artifacts": len(artifacts),
        "search_results": by_type.get("search_result", 0),
        "opened": opened,
        "profiles": len(profiles),
        "blocked": statuses.get("blocked", 0),
        "failed": statuses.get("failed", 0),
        "platforms": len({a.get("platform") for a in artifacts if a.get("platform")}),
    }


def build_markdown(run: dict, artifacts: list[dict], findings: list[dict], profiles: list[dict], entities: list[dict]) -> str:
    stats = _stats(run, artifacts, findings, profiles)
    cog = cognitive.evaluate(profiles, artifacts, entities)
    evidence_ids = {a["artifact_id"] for a in artifacts}
    dims = ", ".join(f"{key}={value['confidence']}" for key, value in cog.items())
    now = datetime.now(UTC).strftime("%Y-%m-%d")

    return f"""# รายงานการพัฒนาต้นแบบ Agentic OSINT

- วันที่จัดทำ: {now}
- Run: `{run['id']}`
- เป้าหมายทดลอง: `{run['target']}` ({run['target_type']})
- โปรไฟล์การรัน: {run['profile']}

## บทคัดย่อ

รายงานนี้อธิบายการพัฒนากระบวนการเก็บหลักฐาน OSINT แบบ lead-driven และการสังเคราะห์ Subject Intelligence Dossier พร้อม 6D Cognitive Profiling จากหลักฐานที่อ้างกลับได้ ในรอบนี้เก็บ artifact {stats['artifacts']} ชิ้น เปิดอ่านสำเร็จ {stats['opened']} หน้า พบโปรไฟล์ {stats['profiles']} แห่ง ครอบคลุม {stats['platforms']} แพลตฟอร์ม และมีหลักฐานอ้างอิง {len(evidence_ids)} รายการ

## 1. บทนำ

ต้นแบบเดิมมีเครื่องมือจำนวนหนึ่งแต่ไม่มีขั้นตอนสกัดโปรไฟล์และต่อยอดจากผลค้น รายงานนี้จึงปรับแกนกลางเป็น corpus ของ artifact ที่มีที่มา เวลา hash และระดับความมั่นใจ ก่อนสกัดเอนทิตีและสังเคราะห์รายงาน

## 2. ทฤษฎีและงานที่เกี่ยวข้อง

- ReAct: วางแผน–เรียกเครื่องมือ–รับผลย้อนกลับ
- Toolformer: การใช้เครื่องมือภายนอกเสริมโมเดล
- WebArena: การประเมินภารกิจหลายขั้นตอนด้วยเกณฑ์ตรวจสอบได้
- Berkeley Protocol: ที่มา บริบท และการตรวจสอบหลักฐาน

## 3. วิธีดำเนินการ

กระบวนการ: normalize → สร้างสมมติฐานคำค้น → ค้นหลายเครื่องยนต์ → จัดอันดับ → เปิดอ่านด้วย Moli → สกัดเอนทิตี → สร้าง lead → pivot → ตรวจความขัดแย้ง → สังเคราะห์ dossier

### 3.1 การเก็บข้อมูล
- search result เก็บเป็น artifact ระดับ Unverified
- เปิดอ่านหน้าโปรไฟล์/โพสต์ด้วย headless browser และบันทึก hash
- ใช้ vendor scanner เป็นแหล่ง metadata และ probe แพลตฟอร์มเพิ่มในโหมด standard/deep

### 3.2 การวิเคราะห์
- profile resolver รวมข้อมูลตาม platform+username
- contradiction ตรวจชื่อ/สถานที่ขัดกัน
- 6D Profiling ใช้สถิติข้อความและหลักฐานจริง โดยติดป้าย Speculative เมื่อไม่พอ

### 3.3 ตัวชี้วัด
- จำนวน artifact, หน้าที่เปิดได้, โปรไฟล์, pivots, ฟิลด์ที่สกัดได้, จำนวน blocked/failed
- ความครอบคลุมของ 6D: {dims}

## 4. ผลการวิจัย

### 4.1 สถิติการรัน

| ตัวชี้วัด | ค่า |
|---|---|
| artifact ทั้งหมด | {stats['artifacts']} |
| ผลค้น | {stats['search_results']} |
| หน้าถูกเปิดอ่าน | {stats['opened']} |
| โปรไฟล์ | {stats['profiles']} |
| แพลตฟอร์ม | {stats['platforms']} |
| blocked | {stats['blocked']} |
| failed | {stats['failed']} |

### 4.2 ผลการวิเคราะห์ 6D
""" + "\n".join(
        f"- **{key}** ({value['confidence']}): {value['assessment']}" for key, value in cog.items()
    ) + """

### 4.3 ข้อจำกัด
- ข้อมูลจากสาธารณะเท่านั้น; หน้า blocked ไม่ถูกตีความเป็น "ไม่พบ"
- OCEAN เป็นสมมติฐานจากสถิติข้อความ
- ตัวเลขเป็นของ run นี้ ไม่ใช่ค่าเฉลี่ยของทั้งระบบ

## 5. อภิปรายผล

คุณภาพผลขึ้นกับปริมาณร่องรอยสาธารณะและความสามารถเปิดหน้าได้ การเพิ่มจำนวนรอบมีประโยชน์เมื่อมี lead ใหม่จริง มิฉะนั้นเพิ่มเวลาโดยไม่เพิ่มหลักฐาน รายงาน dossier จึงต้องแยกข้อเท็จจริง ความอนุมาน และข้อจำกัด

## 6. สรุปและข้อเสนอแนะ

- ใช้ dossier เพื่อตรวจสอบ ไม่ใช่ชี้ขาดตัวบุคคล
- เก็บ run ที่มีคำตอบอ้างอิงเพื่อวัด precision/recall ระยะถัดไป
- เพิ่มแหล่งข้อมูลที่ต้องล็อกอินแบบมีสิทธิ์ และบันทึกเวอร์ชันเครื่องมือ

## เอกสารอ้างอิง

- Yao et al. (2023) ReAct. ICLR
- Schick et al. (2023) Toolformer. NeurIPS
- Zhou et al. (2024) WebArena. ICLR
- OHCHR & HRC (2022) Berkeley Protocol
"""


def to_docx(markdown: str, path: str | Path) -> Path:
    from docx import Document

    document = Document()
    for line in markdown.splitlines():
        if line.startswith("# "):
            document.add_heading(line[2:].strip(), level=0)
        elif line.startswith("### "):
            document.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "):
            document.add_heading(line[3:].strip(), level=1)
        elif line.startswith("|"):
            document.add_paragraph(line)
        elif line.startswith("- "):
            document.add_paragraph(line[2:].strip(), style="List Bullet")
        elif line.strip():
            document.add_paragraph(line)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(target)
    return target
