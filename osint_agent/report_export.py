"""
ส่งออกรายงานเป็น HTML พร้อมพิมพ์ (เปิดแล้ว Ctrl+P → Save as PDF)

ใช้ HTML แทนไลบรารี PDF เพราะ Application Control ของเครื่องบล็อก DLL ของ fontTools
และเบราว์เซอร์จัดฟอนต์ไทย (สระ/วรรณยุกต์) ได้ถูกต้องกว่าไลบรารี PDF ทั่วไป
"""

import html
from datetime import datetime

import markdown

PRINT_CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'Sarabun', 'Leelawadee UI', 'Tahoma', sans-serif; color: #1a1a1a;
       font-size: 11pt; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 24px; }
.header { border-bottom: 3px double #8a6d3b; padding-bottom: 10px; margin-bottom: 18px; }
.header .title { font-size: 20pt; font-weight: 700; letter-spacing: .03em; }
.header .sub { color: #666; font-size: 9.5pt; }
.meta { width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 10pt; }
.meta td { border: 1px solid #ccc; padding: 5px 9px; vertical-align: top; }
.meta td:first-child { background: #f5f1e8; width: 28%; font-weight: 600; }
h2 { font-size: 13pt; border-bottom: 1px solid #8a6d3b; padding-bottom: 3px; margin-top: 20px;
     page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 10pt; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
th { background: #f5f1e8; }
code { background: #f3f3f3; padding: 0 4px; border-radius: 3px; font-size: 9.5pt; }
li { margin-bottom: 3px; }
.steps { font-size: 9pt; color: #444; columns: 2; column-gap: 24px; }
.footer { margin-top: 28px; border-top: 1px solid #ccc; padding-top: 8px; font-size: 8.5pt; color: #666; }
.print-hint { background: #fff8e1; border: 1px solid #e0c97f; padding: 8px 12px; font-size: 10pt;
              margin-bottom: 16px; }
@media print { .print-hint { display: none; } body { padding: 0; } }
"""


def build_report_html(
    report_md: str,
    identifier_type: str,
    identifier_value: str,
    context: str = "",
    steps: list | None = None,
    stats: dict | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    body = markdown.markdown(report_md or "", extensions=["tables", "sane_lists"])
    esc = html.escape

    meta_rows = [
        ("เป้าหมาย", f"{esc(identifier_type)}: <code>{esc(identifier_value)}</code>"),
        ("บริบท", esc(context) if context else "—"),
        ("วันเวลาที่สร้าง", generated_at.strftime("%d/%m/%Y %H:%M:%S")),
    ]
    if stats:
        meta_rows.append(
            ("การทำงานของ agent", f"ค้นเว็บ {stats.get('search', 0)} ครั้ง · เรียกเครื่องมือ {stats.get('tool', 0)} ครั้ง")
        )
    meta_html = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in meta_rows)

    steps_html = ""
    if steps:
        items = "".join(f"<li>{esc(s)}</li>" for s in steps[:80])
        steps_html = f"<h2>บันทึกขั้นตอนการสืบสวน</h2><ol class='steps'>{items}</ol>"

    return f"""<!DOCTYPE html>
<html lang="th"><head><meta charset="utf-8">
<title>รายงาน OSINT — {esc(identifier_value)}</title>
<style>{PRINT_CSS}</style></head>
<body>
<div class="print-hint">พิมพ์เป็น PDF: กด <b>Ctrl+P</b> แล้วเลือก <b>Save as PDF</b></div>
<div class="header">
  <div class="title">รายงานการสืบสวนเบื้องต้นด้วยข้อมูลสาธารณะ (OSINT)</div>
  <div class="sub">สร้างโดยระบบ OSINT Lookup · ข้อมูลจาก AI ต้องตรวจสอบยืนยันก่อนนำไปใช้</div>
</div>
<table class="meta">{meta_html}</table>
{body}
{steps_html}
<div class="footer">
รายงานนี้รวบรวมจากข้อมูลสาธารณะโดยระบบอัตโนมัติ อาจมีข้อผิดพลาด ใช้เป็นข้อมูลประกอบการตรวจสอบเบื้องต้นเท่านั้น
ไม่ใช่พยานหลักฐานโดยตรง · ห้ามนำไปใช้คุกคาม สะกดรอย หรือละเมิดสิทธิส่วนบุคคล ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล (PDPA)
</div>
</body></html>"""
