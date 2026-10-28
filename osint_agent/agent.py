"""
ReAct agent — โมเดลคิด วางแผน และเลือกเครื่องมือเองเป็นทอด ๆ

ลูป: คิด → เลือก tool → เห็นผล → คิดต่อ → ... → สรุปเป็นรายงาน
ทั้ง web_search (API รันให้) และ tool ในเครื่อง (tools.py) อยู่ในลิสต์เดียวกัน
"""

import json
import os

from anthropic import Anthropic

from .system_prompt import SYSTEM_PROMPT
from .enhanced_system_prompt import ENHANCED_SYSTEM_PROMPT
from .tools import build_tool_list, execute_tool
from .identity_triangulation import IdentityTriangulator

MODEL = "claude-sonnet-5"
MAX_STEPS = 16
MAX_WEB_SEARCHES = 10
STEP_MAX_TOKENS = 4096
REPORT_MAX_TOKENS = 8192
MAX_TOOL_RESULT_CHARS = 14000


def read_config() -> dict:
    """อ่าน .env ที่ root โปรเจกต์ (ค่ามีผลเฉพาะโปรเจกต์นี้ ไม่แตะ env ระดับเครื่อง)"""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
    )
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _build_client(api_key_override: str = None) -> Anthropic:
    config = read_config()

    # ลำดับความสำคัญ:
    # 1. override จาก frontend (ถ้ามี)
    # 2. จาก .env หรือ environment
    # 3. ถ้าไม่มี ไม่ต้อง raise error ให้ใช้ default
    api_key = api_key_override or config.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")

    # ถ้าไม่มี API key และไม่มี base_url ที่อนุญาต ให้ raise error
    base_url = config.get("ANTHROPIC_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")

    # If MaxPlus base_url is set, it's optional to have API key (MaxPlus might use auth headers)
    # But for standard Anthropic, we need the key
    if not api_key and not base_url:
        raise RuntimeError(
            "ไม่พบ ANTHROPIC_API_KEY (ทั้งใน .env และตัวแปรแวดล้อม) กรุณาตั้งค่าก่อนใช้งาน"
        )

    # ใช้ placeholder key ถ้า base_url เป็น MaxPlus แต่ไม่มี explicit key
    if not api_key and base_url and "maxplus" in base_url.lower():
        api_key = "placeholder-key"  # MaxPlus ไม่จำเป็นต้องใช้ key ถ้ากำหนด base_url

    if base_url:
        return Anthropic(api_key=api_key or "sk-placeholder", base_url=base_url)
    return Anthropic(api_key=api_key)


def _extract_text(content_blocks) -> str:
    return "".join(
        block.text for block in content_blocks if getattr(block, "type", None) == "text"
    )


def _build_tools():
    return [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": MAX_WEB_SEARCHES,
        },
        *build_tool_list(),
    ]


def _run_tool_calls(content_blocks) -> list:
    """รัน client-side tool ทุกตัวที่โมเดลขอ แล้วคืน tool_result blocks (พร้อมรูปถ้ามี)"""
    results = []
    for block in content_blocks:
        if getattr(block, "type", None) != "tool_use":
            continue
        name = getattr(block, "name", "")
        tool_input = getattr(block, "input", None) or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        outcome = execute_tool(name, tool_input)
        output = outcome.get("output", "") if isinstance(outcome, dict) else str(outcome)
        images = outcome.get("images", []) if isinstance(outcome, dict) else []

        if len(output) > MAX_TOOL_RESULT_CHARS:
            output = output[:MAX_TOOL_RESULT_CHARS] + "\n[... ผลลัพธ์ยาวเกิน ถูกตัด ...]"

        content = [{"type": "text", "text": output}, *images]
        results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            }
        )
    return results


def _describe(content_blocks) -> list:
    """แปลง content blocks เป็น event สำหรับแสดงผลบนหน้าเว็บ"""
    events = []
    for block in content_blocks:
        btype = getattr(block, "type", None)
        if btype == "server_tool_use":
            query = (getattr(block, "input", None) or {}).get("query", "")
            events.append({"kind": "search", "text": query})
        elif btype == "tool_use":
            name = getattr(block, "name", "?")
            args = json.dumps(getattr(block, "input", {}) or {}, ensure_ascii=False)
            events.append({"kind": "tool", "text": f"{name} — {args[:160]}"})
        elif btype == "text":
            text = (block.text or "").strip()
            if text:
                events.append({"kind": "note", "text": text[:220]})
    return events


def run_osint_lookup(
    identifier_type: str,
    identifier_value: str,
    context: str,
    on_event=None,
    api_keys: dict = None,
):
    """
    รัน ReAct loop แล้วคืนรายงานภาษาไทย

    on_event: callback(event: dict) — เรียกทุกครั้งที่เกิดความคืบหน้า
              event = {"kind": "step"|"search"|"tool"|"result"|"note"|"done", "text": str}
    api_keys: dict — API keys จาก frontend {"anthropic": str, "google": str, "maxplus": str}
    """
    emit = on_event or (lambda _event: None)

    # ใช้ API key จาก frontend ถ้ามี ไม่งั้นใช้จาก .env
    api_keys = api_keys or {}
    client = _build_client(api_key_override=api_keys.get("anthropic"))

    # สร้าง Identity Triangulator สำหรับ session นี้
    triangulator = IdentityTriangulator()

    # เก็บ API keys ใน environment สำหรับ tools
    import os
    if api_keys.get("google"):
        os.environ["GOOGLE_API_KEY"] = api_keys["google"]
    if api_keys.get("google_cx"):
        os.environ["GOOGLE_CX"] = api_keys["google_cx"]

    context_block = (
        f"\n\n# ข้อมูล input ของคำขอนี้\n"
        f"- ประเภท identifier: {identifier_type}\n"
        f"- บริบทจากผู้ใช้: {context if context else '(ไม่มี)'}\n"
    )
    # ใช้ Enhanced System Prompt ที่สอน AI ให้คิดและ chain tools
    system = ENHANCED_SYSTEM_PROMPT + context_block

    messages = [
        {
            "role": "user",
            "content": (
                f"เป้าหมายที่ต้องตรวจสอบ: {identifier_type} = {identifier_value}\n"
                "ดำเนินการสืบสวนเบื้องต้นด้วยเครื่องมือที่คุณมี แล้วสรุปเป็นรายงาน"
            ),
        }
    ]

    tools = _build_tools()
    steps_used = 0

    for step in range(1, MAX_STEPS + 1):
        steps_used = step
        emit({"kind": "step", "text": f"รอบคิดที่ {step}"})

        response = client.messages.create(
            model=MODEL,
            max_tokens=STEP_MAX_TOKENS,
            system=system,
            messages=messages,
            tools=tools,
        )
        messages.append({"role": "assistant", "content": response.content})

        for event in _describe(response.content):
            emit(event)

        if response.stop_reason == "pause_turn":
            continue

        tool_results = _run_tool_calls(response.content)
        if tool_results:
            for result in tool_results:
                first = result["content"][0]["text"] if result["content"] else ""
                if first:  # ตรวจสอบว่า first ไม่เป็น None หรือ empty
                    emit({"kind": "result", "text": first[:200].replace("\n", " ")})
            messages.append({"role": "user", "content": tool_results})
            continue

        if response.stop_reason == "max_tokens":
            messages.append(
                {
                    "role": "user",
                    "content": "คำตอบถูกตัดกลางคัน ให้เขียนรายงานต่อจากจุดที่ขาด โดยไม่ต้องใช้เครื่องมือเพิ่ม",
                }
            )
            continue

        break

    emit({"kind": "step", "text": "สังเคราะห์รายงาน"})

    messages.append(
        {
            "role": "user",
            "content": (
                "หยุดใช้เครื่องมือแล้ว เขียนรายงานสรุปภาษาไทยตามหัวข้อ "
                '"รูปแบบรายงานผลลัพธ์" ใน system prompt ให้ครบทุกหัวข้อ '
                "โดยอ้างอิงเฉพาะข้อมูลที่เก็บได้จริง ห้ามแต่งข้อมูลที่ไม่มีหลักฐาน "
                "และระบุคำค้น/เครื่องมือที่ใช้เป็นหลักฐานประกอบด้วย"
            ),
        }
    )

    final_response = client.messages.create(
        model=MODEL,
        max_tokens=REPORT_MAX_TOKENS,
        system=system,
        messages=messages,
    )

    report = _extract_text(final_response.content).strip()
    if not report:
        report = "ไม่สามารถสร้างรายงานได้ กรุณาลองใหม่อีกครั้ง"

    emit({"kind": "done", "text": f"เสร็จสิ้น ({steps_used} รอบ)"})
    return report
