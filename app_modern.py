"""OSINT Lookup — Modern UI matching landing page theme"""

import html
import re
from datetime import datetime
import streamlit as st

from osint_agent.access import audit
from osint_agent.agent import (
    MODEL, _build_client, _client_overrides, _configured_model,
    list_provider_models, run_osint_lookup,
)
from osint_agent.graph import build_graph_html, build_relationship_graph
from osint_agent.report_export import build_report_html

st.set_page_config(page_title="OSINT Lookup", page_icon="◆", layout="wide", initial_sidebar_state="collapsed")

# Main Investigation UI (ไม่ต้อง login)
ACTOR = {"name": "user", "unit": "-"}

# Modern Color Palette (matching landing.html)
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Sarabun:wght@300;400;600;700&display=swap');

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body, [class*="css"], .stMarkdown, input, textarea, select, button {
    font-family: 'Sarabun', 'Inter', sans-serif !important;
}

body {
    background: #0a0e1a !important;
    color: #e8eaed !important;
}

/* Hide Streamlit branding */
#MainMenu, footer, header [data-testid="stToolbar"] { visibility: hidden; }
.block-container { padding-top: 2rem; max-width: 1200px; }

/* Remove overlapping boxes */
[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* Remove Streamlit default card backgrounds */
.stMarkdown, .element-container {
    background: transparent !important;
}

/* Ensure no extra boxes appear */
section[data-testid="stSidebar"] > div {
    background: transparent !important;
}

div[data-testid="column"] {
    background: transparent !important;
}

/* Login Page */
.login-container {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
}

.brand-mark {
    font-size: 4rem;
    color: #C9A96E;
    margin-bottom: 1rem;
    animation: fadeIn 0.8s ease-out;
}

.brand-title {
    font-size: 3rem;
    font-weight: 700;
    color: #e8eaed;
    margin-bottom: 0.5rem;
}

.brand-subtitle {
    font-size: 1.1rem;
    color: #9aa0a6;
    margin-bottom: 3rem;
}

.login-card {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    max-width: 450px;
    width: 100%;
}

.login-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 2rem;
    font-size: 1.5rem;
    font-weight: 600;
}

/* Form Inputs */
.stTextInput > div > div > input,
.stSelectbox > div > div > select {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 0.5rem !important;
    color: #e8eaed !important;
    padding: 0.875rem 1rem !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
}

.stTextInput > div > div > input:focus,
.stSelectbox > div > div > select:focus {
    border-color: #00d9ff !important;
    box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.1) !important;
    background: rgba(255, 255, 255, 0.05) !important;
}

.stTextInput > div > div > input::placeholder {
    color: #6b7280 !important;
}

/* Labels */
.stTextInput label, .stSelectbox label {
    color: #9aa0a6 !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    margin-bottom: 0.5rem !important;
}

/* Buttons */
.stButton > button {
    background: #00d9ff !important;
    color: #0a0e1a !important;
    border: none !important;
    border-radius: 0.5rem !important;
    padding: 0.875rem 2rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 20px rgba(0, 217, 255, 0.3) !important;
    width: 100%;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 30px rgba(0, 217, 255, 0.5) !important;
    background: #00c4e6 !important;
}

/* Investigation Card */
.inv-card {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin-bottom: 2rem;
}

.inv-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.inv-icon {
    font-size: 2.5rem;
}

.inv-title {
    font-size: 2rem;
    font-weight: 700;
    color: #00d9ff;
}

.badge {
    display: inline-flex;
    align-items: center;
    padding: 0.4rem 1rem;
    border-radius: 9999px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-left: auto;
}

.badge-success {
    background: rgba(76, 175, 80, 0.15);
    color: #4CAF50;
}

.badge-info {
    background: rgba(0, 217, 255, 0.15);
    color: #00d9ff;
}

/* Timeline */
.timeline {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 1rem;
    padding: 1.5rem;
    max-height: 600px;
    overflow-y: auto;
}

.timeline-item {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    animation: slideInLeft 0.3s ease-out backwards;
}

@keyframes slideInLeft {
    from { opacity: 0; transform: translateX(-20px); }
    to { opacity: 1; transform: translateX(0); }
}

.timeline-icon {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 0.875rem;
}

.timeline-icon.success {
    background: rgba(76, 175, 80, 0.15);
    color: #4CAF50;
}

.timeline-icon.loading {
    background: rgba(0, 217, 255, 0.15);
    color: #00d9ff;
    animation: spin 2s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.timeline-title {
    font-weight: 600;
    color: #e8eaed;
    margin-bottom: 0.25rem;
}

.timeline-desc {
    color: #9aa0a6;
    font-size: 0.875rem;
}

/* Report */
.report {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 1rem;
    padding: 2rem;
    max-height: 600px;
    overflow-y: auto;
    animation: fadeIn 0.5s ease-out;
}

.report h2 {
    font-size: 1.5rem;
    color: #e8eaed;
    margin-top: 2rem;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.report h2:first-child {
    margin-top: 0;
}

.report p {
    margin-bottom: 1rem;
    line-height: 1.8;
    color: #9aa0a6;
}

.report ul {
    list-style: none;
    padding-left: 1rem;
}

.report li {
    margin-bottom: 0.5rem;
    color: #9aa0a6;
}

.report li::before {
    content: '▸';
    color: #00d9ff;
    margin-right: 0.5rem;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 2rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #9aa0a6 !important;
    border-bottom: 2px solid transparent !important;
    padding: 1rem 0 !important;
    font-weight: 500 !important;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #e8eaed !important;
}

.stTabs [aria-selected="true"] {
    color: #00d9ff !important;
    border-bottom-color: #00d9ff !important;
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: #0a0e1a;
}

::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 217, 255, 0.3);
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
</style>
""",
    unsafe_allow_html=True,
)


# Main Investigation UI
st.markdown(
    """
<div class="brand-mark" style="text-align: center; font-size: 3rem; margin-bottom: 0.5rem;">◆</div>
<h1 style="text-align: center; font-size: 2.5rem; margin-bottom: 0.5rem;">OSINT Lookup</h1>
<p style="text-align: center; color: #9aa0a6; margin-bottom: 3rem;">Intelligence-Grade Investigation Platform</p>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="inv-card">', unsafe_allow_html=True)
st.markdown("### 🎯 เริ่มการสืบสวน", unsafe_allow_html=True)

# API Key Configuration
with st.expander("⚙️ ตั้งค่า API Keys (Optional — ใช้ config จาก .env หากไม่กำหนด)", expanded=False):
    st.info("💡 ระบบจะใช้ .env configuration เป็นค่าเริ่มต้น คุณสามารถ override ได้ด้านล่าง")

    providers = {
        "ใช้ .env / Anthropic (ค่าเดิม)": ("", "", ""),
        "MaxPlus GPT": ("openai", "https://api.maxplus-ai.cc/v1", ""),
        "MaxPlus GPT Pro Ultimate Lite": ("openai", "https://api.maxplus-ai.cc/gpt-pro-ultimate-lite/v1", ""),
        "MaxPlus Claude": ("anthropic", "https://api.maxplus-ai.cc", "claude-sonnet-4-6"),
    }
    selection = st.selectbox("ผู้ให้บริการ AI", list(providers), key="api_provider")
    provider, default_base, default_model = providers[selection]
    anthropic_key = st.text_input(
        "Anthropic/MaxPlus API Key",
        type="password",
        placeholder="sk-ant-api03-... หรือ ccsk-...",
        help="Override Anthropic/MaxPlus key จาก .env (ถ้าไม่กำหนด ให้ใช้จาก .env)",
        key="anthropic_api_key"
    )
    base_url = st.text_input(
        "API Base URL", value=default_base, key=f"api_base_url_{selection}",
        placeholder="เว้นว่างเพื่อใช้ .env หรือ Anthropic โดยตรง",
        help="MaxPlus GPT ใช้ https://api.maxplus-ai.cc/v1 หรือ URL ของ pool จาก Dashboard",
    ).strip()
    if provider:
        st.caption("API key ต้องมีสิทธิ์ใช้ pool ที่เลือกใน MaxPlus Dashboard")
    model_settings = {
        "anthropic": anthropic_key.strip() or st.session_state.get("saved_anthropic_key", ""),
        "provider": provider, "base_url": base_url,
    }
    models_key = f"available_models_{selection}_{base_url}"
    if st.button("โหลดรายการโมเดล / ตรวจสอบ key", key="load_provider_models"):
        try:
            with st.spinner("กำลังตรวจสอบ key และโหลดโมเดล…"):
                models = list_provider_models(model_settings)
                if not models:
                    raise RuntimeError("ไม่พบโมเดลสำหรับ key นี้ กรุณาตรวจ pool ใน Dashboard")
                st.session_state[models_key] = models
            st.success("โหลดรายการโมเดลสำเร็จ กรุณาเลือก Model ID ก่อนเริ่มสืบสวน")
        except Exception as exc:
            st.session_state.pop(models_key, None)
            st.error(f"เชื่อมต่อไม่สำเร็จ: {exc}")
    available_models = st.session_state.get(models_key, [])
    if available_models:
        model = st.selectbox(
            "Model ID", available_models, index=None, placeholder="เลือกโมเดลที่ต้องการใช้งาน",
            key=f"api_model_list_{models_key}",
        )
        st.caption("โหลดรายการสำเร็จยังไม่ได้ทดสอบว่าโมเดลสร้างข้อความหรือใช้เครื่องมือได้")
    else:
        model = st.text_input(
            "Model ID", value=default_model, key=f"api_model_{selection}",
            placeholder="โหลดรายการโมเดลด้านบน หรือกรอก ID จาก Dashboard",
            help=f"เว้นว่างเพื่อใช้ OSINT_MODEL จาก .env; Anthropic เดิมใช้ {MODEL}",
        ).strip()

    st.markdown("**Google Search API (Optional)**")
    google_key = st.text_input(
        "Google API Key",
        type="password",
        placeholder="AIzaSy...",
        help="เก็บการตั้งค่าเดิมไว้ได้ ปัจจุบันการค้นหาใช้ DuckDuckGo โดยไม่ต้องใช้ Google key",
        key="google_api_key"
    )
    google_cx = st.text_input(
        "Google Custom Search Engine ID",
        placeholder="0123456789abcdef:...",
        help="Search Engine ID สำหรับ Google Custom Search",
        key="google_cx"
    )

    if st.button("💾 บันทึก API Keys"):
        if provider == "openai" and not model:
            st.error("กรุณาโหลดรายการโมเดลหรือกรอก Model ID ก่อนบันทึก")
        else:
            for name, value in (("anthropic_key", anthropic_key), ("google_key", google_key),
                                ("google_cx", google_cx)):
                if value.strip():
                    st.session_state[f"saved_{name}"] = value.strip()
            for name, value in (("provider", provider), ("base_url", base_url), ("model", model)):
                st.session_state[f"saved_{name}"] = value
            st.success("✓ บันทึกการตั้งค่า API ใน session นี้แล้ว")

st.markdown("---")


TYPES = {
    "เบอร์โทรศัพท์": "0812345678",
    "อีเมล": "example@domain.com",
    "ชื่อ": "นาย สมชาย ใจดี",
    "Username": "@username หรือ URL โปรไฟล์",
    "URL/โดเมน": "https://example.com",
    "เลขบัญชี": "123-4-56789-0",
}

with st.form("investigate"):
    col1, col2 = st.columns([1, 2])
    with col1:
        identifier_type = st.selectbox("ประเภท", list(TYPES.keys()))
    with col2:
        identifier_value = st.text_input(
            "ค่าที่ต้องการตรวจสอบ", placeholder=TYPES[identifier_type]
        )

    submitted = st.form_submit_button("เริ่มสืบสวน  →")
    context = ""

st.markdown('</div>', unsafe_allow_html=True)


def _current_api_keys():
    return {
        name: value
        for name, value in (
            ("anthropic", anthropic_key.strip() or st.session_state.get("saved_anthropic_key", "")),
            ("google", google_key.strip() or st.session_state.get("saved_google_key", "")),
            ("google_cx", google_cx.strip() or st.session_state.get("saved_google_cx", "")),
            ("provider", provider),
            ("base_url", base_url),
            ("model", model),
        )
        if value
    }


def _timeline_html(events):
    items = []
    for event in events:
        kind = event.get("kind", "note")
        text = html.escape(event.get("text", ""))
        if kind in ("search", "tool", "done"):
            icon = {"search": "🔍", "tool": "⚙️", "done": "✓"}[kind]
            state = "success" if kind == "done" else "loading"
            items.append(
                f'<div class="timeline-item"><div class="timeline-icon {state}">{icon}</div>'
                f'<div><div class="timeline-title">{text}</div></div></div>'
            )
        elif kind == "result" and items:
            items[-1] = items[-1].replace("loading", "success")
    return '<div class="timeline">' + "".join(items) + "</div>"


if submitted:
    value = identifier_value.strip()
    if not value:
        st.warning("กรุณากรอกค่าที่ต้องการตรวจสอบ")
        st.stop()
    if available_models and not model:
        st.warning("กรุณาเลือก Model ID ในหน้าตั้งค่า API ก่อนเริ่มสืบสวน")
        st.stop()

    audit("search", ACTOR, target_type=identifier_type, target_value=value, context=context.strip())
    st.session_state.setdefault("history", []).append(
        {"type": identifier_type, "value": value, "time": datetime.now().strftime("%H:%M")}
    )
    st.session_state["investigation"] = {
        "type": identifier_type,
        "value": value,
        "context": context,
        "generated_at": datetime.now(),
        "status": "running",
        "events": [],
        "report": "",
        "graph": {"nodes": [], "edges": []},
        "graph_html": None,
        "graph_error": "",
        "error": "",
    }

result = st.session_state.get("investigation")
if result:
    st.markdown("---")
    badge = st.empty()
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        st.markdown("#### 📋 Timeline")
        timeline_container = st.empty()
    with right:
        st.markdown("#### 📊 รายงาน")
        report_area = st.empty()

    if submitted:
        badge.info(f"⏳ กำลังตรวจสอบ {result['value']}")
        report_area.info("AI กำลังเลือกเครื่องมือและรวบรวมหลักฐาน...")

        def on_event(event):
            result["events"].append({
                "kind": event.get("kind", "note"),
                "text": str(event.get("text", "")),
            })
            timeline_container.markdown(_timeline_html(result["events"]), unsafe_allow_html=True)

        api_keys = _current_api_keys()
        try:
            result["report"] = run_osint_lookup(
                identifier_type=result["type"],
                identifier_value=result["value"],
                context=result["context"],
                on_event=on_event,
                api_keys=api_keys or None,
            )
            result["status"] = "done"
        except Exception as exc:
            error = str(exc)
            if getattr(exc, "status_code", None) == 401:
                error = "API key ไม่ผ่านการยืนยัน (401) กรุณาตรวจผู้ให้บริการ, Base URL และ key แล้วบันทึกการตั้งค่าอีกครั้ง"
            result.update(status="error", error=error)

        if result["report"]:
            report_area.markdown(result["report"])
            try:
                with st.spinner("กำลังสร้างผังความสัมพันธ์…"):
                    client = _build_client(**_client_overrides(api_keys))
                    try:
                        result["graph"] = build_relationship_graph(
                            client, result["report"], model=_configured_model(api_keys),
                        )
                    finally:
                        client.close()
                    result["graph_html"] = build_graph_html(result["graph"])
            except Exception as exc:
                # A graph failure must not discard the report or its downloads.
                result["graph_error"] = f"สร้างผังความสัมพันธ์ไม่สำเร็จ ({type(exc).__name__})"

    timeline_container.markdown(_timeline_html(result["events"]), unsafe_allow_html=True)
    if result["error"]:
        report_area.empty()
        badge.error(f"ตรวจสอบไม่สำเร็จ: {result['value']}")
        st.error(f"เกิดข้อผิดพลาด: {result['error']}")
    elif result["report"]:
        badge.success(f"✓ ตรวจสอบเสร็จสิ้น: {result['value']}")
        report_area.markdown(result["report"])
        st.markdown("---")
        tab_report, tab_graph, tab_export = st.tabs(
            ["📄 รายงานเต็ม", "🕸️ ผังความสัมพันธ์", "💾 ส่งออก"]
        )
        with tab_report:
            st.markdown(result["report"])
        with tab_graph:
            if result["graph_error"]:
                st.warning(result["graph_error"])
            elif result["graph_html"]:
                st.components.v1.html(result["graph_html"], height=560, scrolling=False)
                graph = result["graph"]
                st.caption(f"{len(graph['nodes'])} โหนด · {len(graph.get('edges') or [])} ความสัมพันธ์")
            else:
                st.info("รายงานนี้ยังไม่มีความสัมพันธ์ที่ยืนยันได้")
        with tab_export:
            col1, col2 = st.columns(2)
            filename = re.sub(r"[^\w.-]", "_", result["value"][:20])
            with col1:
                html_export = build_report_html(
                    report_md=result["report"],
                    identifier_type=result["type"],
                    identifier_value=result["value"],
                    context=result["context"],
                    steps=[
                        event["text"] for event in result["events"]
                        if event["kind"] in ("search", "tool", "done")
                    ],
                    stats={
                        kind: sum(event["kind"] == kind for event in result["events"])
                        for kind in ("search", "tool")
                    },
                    generated_at=result["generated_at"],
                )
                st.download_button(
                    "📥 ดาวน์โหลด HTML", html_export,
                    file_name=f"report_{filename}.html", mime="text/html", use_container_width=True,
                )
            with col2:
                st.download_button(
                    "📥 ดาวน์โหลด Markdown", result["report"],
                    file_name=f"report_{filename}.md", mime="text/markdown", use_container_width=True,
                )
