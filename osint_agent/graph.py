"""
แปลงรายงาน OSINT เป็นกราฟความสัมพันธ์ (entity-relationship graph)

แยกเป็นฟังก์ชันเดี่ยว เพื่อไม่ให้ปนกับลูป ReAct — รับข้อความรายงานที่เสร็จแล้ว
แล้วให้โมเดลสกัดเฉพาะ "ความสัมพันธ์ที่มีหลักฐานรองรับ" ออกมาเป็น JSON
"""

import json
import re

from .agent import MODEL

GRAPH_MAX_TOKENS = 2048

GRAPH_PROMPT = """คุณเป็นตัวสกัดข้อมูลสำหรับสร้างกราฟความสัมพันธ์

จากรายงาน OSINT ด้านล่าง ให้สกัดเฉพาะความสัมพันธ์ที่มีหลักฐานระบุไว้ในรายงานเท่านั้น
ห้ามสร้างความสัมพันธ์ที่ไม่มีในรายงาน ห้ามเดา

ตอบเป็น JSON เท่านั้น ตามรูปแบบนี้:
{
  "nodes": [
    {"id": "ent1", "label": "ชื่อที่แสดง", "group": "identifier|account|person|page|source|other"}
  ],
  "edges": [
    {"from": "ent1", "to": "ent2", "label": "ความสัมพันธ์สั้นๆ", "confidence": "high|medium|low"}
  ]
}

กฎ:
- ต้องมี node ของเป้าหมายหลัก (identifier ที่ค้น) เสมอ และใช้ id = "target"
- ใส่ node เฉพาะที่มีอยู่จริงในรายงาน (เช่น เพจที่พบ, บัญชีที่เชื่อมโยง, แหล่งข่าว)
- edge label ต้องสั้นไม่เกิน 25 ตัวอักษร และอธิบายความสัมพันธ์จริง เช่น "เจ้าของบัญชี", "โพสต์เตือนภัยใน", "อ้างว่าเป็น"
- ถ้ารายงานไม่มีข้อมูลเชื่อมโยงเลย ให้ตอบ {"nodes": [target], "edges": []}
- ตอบ JSON ล้วน ไม่ต้องมีคำอธิบายหรือ markdown fence
"""

ALLOWED_GROUPS = {"identifier", "account", "person", "page", "source", "other"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def _parse_json_block(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"nodes": [], "edges": []}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"nodes": [], "edges": []}
    return data if isinstance(data, dict) else {"nodes": [], "edges": []}


def _sanitize(data: dict) -> dict:
    nodes, seen = [], set()
    for node in data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id", "")).strip()
        label = str(node.get("label", "")).strip()
        if not node_id or not label or node_id in seen:
            continue
        seen.add(node_id)
        group = str(node.get("group", "other")).strip().lower()
        nodes.append(
            {
                "id": node_id,
                "label": label[:60],
                "group": group if group in ALLOWED_GROUPS else "other",
            }
        )

    edges = []
    for edge in data.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from", "")).strip()
        dst = str(edge.get("to", "")).strip()
        if src not in seen or dst not in seen or src == dst:
            continue
        confidence = str(edge.get("confidence", "low")).strip().lower()
        edges.append(
            {
                "from": src,
                "to": dst,
                "label": str(edge.get("label", ""))[:25],
                "confidence": confidence if confidence in ALLOWED_CONFIDENCE else "low",
            }
        )

    return {"nodes": nodes, "edges": edges}


def build_relationship_graph(client, report: str) -> dict:
    """เรียกโมเดลสกัดกราฟจากรายงาน คืน {"nodes": [...], "edges": [...]}"""
    if not report or not report.strip():
        return {"nodes": [], "edges": []}

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=GRAPH_MAX_TOKENS,
            system=GRAPH_PROMPT,
            messages=[{"role": "user", "content": report}],
        )
    except Exception:  # noqa: BLE001 — กราฟเป็นของแถม ไม่ควรทำให้รายงานพัง
        return {"nodes": [], "edges": []}

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return _sanitize(_parse_json_block(text))


GROUP_COLORS = {
    "identifier": "#d62728",   # แดง = เป้าหมายหลัก
    "account": "#ff7f0e",      # ส้ม = บัญชี
    "person": "#1f77b4",       # น้ำเงิน = บุคคล
    "page": "#2ca02c",         # เขียว = เพจ
    "source": "#7f7f7f",       # เทา = แหล่งข่าว
    "other": "#9467bd",        # ม่วง = อื่นๆ
}

CONFIDENCE_STYLE = {
    "high": {"width": 3, "dashes": False},
    "medium": {"width": 2, "dashes": [6, 4]},
    "low": {"width": 1, "dashes": [3, 5]},
}


def build_graph_html(graph: dict, height: int = 520) -> str | None:
    """สร้าง HTML ของกราฟด้วย pyvis — คืน None ถ้าไม่มีข้อมูลพอจะวาด"""
    nodes = graph.get("nodes") or []
    if len(nodes) < 2:
        return None

    from pyvis.network import Network

    net = Network(height=f"{height}px", width="100%", bgcolor="#ffffff", font_color="#222")
    net.barnes_hut(gravity=-6000, central_gravity=0.25, spring_length=180)

    for node in nodes:
        group = node["group"]
        net.add_node(
            node["id"],
            label=node["label"],
            color=GROUP_COLORS.get(group, GROUP_COLORS["other"]),
            size=32 if group == "identifier" else 22,
            font={"size": 15},
            title=f"{node['label']} ({group})",
        )

    for edge in graph.get("edges") or []:
        style = CONFIDENCE_STYLE.get(edge["confidence"], CONFIDENCE_STYLE["low"])
        net.add_edge(
            edge["from"],
            edge["to"],
            label=edge["label"],
            width=style["width"],
            dashes=style["dashes"],
            arrows="to",
            font={"size": 12, "align": "middle"},
        )

    net.set_options(
        """
        var options = {
          "physics": {"stabilization": {"iterations": 220}},
          "edges": {"smooth": {"type": "dynamic"}},
          "interaction": {"hover": true, "navigationButtons": true}
        }
        """
    )

    html = net.generate_html()
    return html.replace("<body>", '<body style="margin:0;background:#fff">', 1)
