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
from .providers import OpenAICompatibleClient, normalize_base_url

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


def _build_client(api_key_override: str = None, *, base_url_override: str = None,
                  provider_override: str = None):
    config = read_config()
    api_key = (api_key_override or config.get("ANTHROPIC_API_KEY")
               or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    base_url = (base_url_override or config.get("ANTHROPIC_BASE_URL")
                or os.environ.get("ANTHROPIC_BASE_URL") or "").strip()
    provider = (provider_override or config.get("OSINT_PROVIDER")
                or os.environ.get("OSINT_PROVIDER") or "anthropic").strip().lower()
    if provider not in ("anthropic", "openai"):
        raise ValueError("OSINT_PROVIDER ต้องเป็น anthropic หรือ openai")
    if not api_key:
        raise RuntimeError(
            "ไม่พบ API key กรุณาบันทึกในหน้าตั้งค่า API หรือกำหนด ANTHROPIC_API_KEY ใน .env"
        )
    if api_key.startswith("ccsk-") and not base_url:
        raise RuntimeError("Key ของ MaxPlus ต้องใช้ Base URL ของ MaxPlus กรุณาเลือกผู้ให้บริการและบันทึกการตั้งค่า")
    if base_url:
        base_url = normalize_base_url(base_url, provider)
    if provider == "openai":
        if not base_url:
            raise RuntimeError("กรุณากำหนด API Base URL สำหรับ API แบบ OpenAI")
        return OpenAICompatibleClient(api_key, base_url)
    if base_url:
        return Anthropic(api_key=api_key, base_url=base_url)
    return Anthropic(api_key=api_key)


def _client_overrides(api_keys):
    return {argument: api_keys[key] for key, argument in (
        ("anthropic", "api_key_override"), ("base_url", "base_url_override"),
        ("provider", "provider_override"),
    ) if api_keys.get(key)}


def _configured_model(api_keys=None):
    api_keys = api_keys or {}
    config = read_config()
    model = api_keys.get("model") or config.get("OSINT_MODEL") or os.environ.get("OSINT_MODEL")
    provider = api_keys.get("provider") or config.get("OSINT_PROVIDER") or os.environ.get("OSINT_PROVIDER")
    if not model and provider == "openai":
        raise RuntimeError("กรุณาโหลดรายการโมเดลหรือกรอก Model ID แล้วบันทึกการตั้งค่า API")
    return (model or MODEL).strip()


def list_provider_models(api_keys):
    client = _build_client(**_client_overrides(api_keys))
    try:
        if isinstance(client, OpenAICompatibleClient):
            return sorted(client.list_models())
        return sorted(item.id for item in client.models.list())
    finally:
        client.close()


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
    api_keys: dict — keys/settings: anthropic, google, google_cx, provider, base_url, model
    """
    emit = on_event or (lambda _event: None)

    # ใช้ API key จาก frontend ถ้ามี ไม่งั้นใช้จาก .env
    api_keys = api_keys or {}
    model = _configured_model(api_keys)
    client = _build_client(**_client_overrides(api_keys))
    try:
        return _run_lookup(client, model, identifier_type, identifier_value, context, emit)
    finally:
        client.close()


def _run_lookup(client, model, identifier_type, identifier_value, context, emit):
    # สร้าง Identity Triangulator สำหรับ session นี้
    triangulator = IdentityTriangulator()

    # Legacy Google settings remain accepted; DuckDuckGo does not require them.

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
            model=model,
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
        model=model,
        max_tokens=REPORT_MAX_TOKENS,
        system=system,
        messages=messages,
    )

    report = _extract_text(final_response.content).strip()
    if not report:
        report = "ไม่สามารถสร้างรายงานได้ กรุณาลองใหม่อีกครั้ง"

    emit({"kind": "done", "text": f"เสร็จสิ้น ({steps_used} รอบ)"})
    return report
