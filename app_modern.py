"""OSINT Lookup — Modern UI matching landing page theme"""

import html
import threading
import time
from datetime import datetime

import streamlit as st

from osint_agent.access import audit
from osint_agent.agent import DEFAULT_MAXPLUS_BASE_URL, _build_client, read_config
from osint_agent.graph import build_graph_html, build_relationship_graph
from osint_agent.profiling import analysis_view
from osint_agent.report_export import build_report_html
from osint_agent.services.orchestrator import Orchestrator
from osint_agent.services.store import RunStore

st.set_page_config(page_title="OSINT Lookup", page_icon="◆", layout="wide", initial_sidebar_state="collapsed")

CONFIG = read_config()

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

    st.markdown("**MaxPlus (แนะนำ)**")
    maxplus_key = st.text_input("MaxPlus API Key", type="password", key="maxplus_api_key")
    maxplus_base = st.text_input(
        "MaxPlus Base URL",
        value=CONFIG.get("MAXPLUS_BASE_URL") or DEFAULT_MAXPLUS_BASE_URL,
        key="maxplus_base_url",
    )
    maxplus_model = st.text_input(
        "MaxPlus Model",
        value=CONFIG.get("MAXPLUS_MODEL") or "claude-sonnet-5-5",
        key="maxplus_model",
    )

    st.markdown("**Claude/Anthropic (ทางเลือก)**")
    anthropic_key = st.text_input("Anthropic API Key", type="password", key="anthropic_api_key")

    if st.button("💾 บันทึก API Keys"):
        saved_count = 0
        for name, value in (
            ("maxplus_key", maxplus_key),
            ("maxplus_base", maxplus_base),
            ("maxplus_model", maxplus_model),
            ("anthropic_key", anthropic_key),
        ):
            if value:
                st.session_state[f"saved_{name}"] = value
                saved_count += 1
        if saved_count:
            st.success(f"✓ บันทึก {saved_count} ค่าแล้ว")
        else:
            st.info("ไม่มีการบันทึก — ระบบจะใช้ .env configuration")

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

    col3, col4 = st.columns(2)
    profile = col3.selectbox("ความลึก", ["quick", "standard", "deep"], index=1, help="standard/deep ใช้ LLM agent เมื่อมี API key")
    trusted_raw = col4.text_input(
        "Verified accounts (คั่นด้วย ,)", placeholder="github:johndoe, email:a@b.com"
    )

    submitted = st.form_submit_button("เริ่มสืบสวน  →")
    context = ""

st.markdown('</div>', unsafe_allow_html=True)

if submitted:
    value = identifier_value.strip()
    if not value:
        st.warning("กรุณากรอกค่าที่ต้องการตรวจสอบ")
        st.stop()

    audit(
        "search",
        ACTOR,
        target_type=identifier_type,
        target_value=value,
        context=context.strip(),
    )

    st.session_state.setdefault("history", []).append(
        {"type": identifier_type, "value": value, "time": datetime.now().strftime("%H:%M")}
    )

    # Investigation UI
    st.markdown("---")
    st.markdown(
        f"""
    <div class="inv-card">
        <div class="inv-header">
            <span class="inv-icon">🔍</span>
            <h2 class="inv-title">{html.escape(value)}</h2>
            <span class="badge badge-info">⏳ กำลังดำเนินการ</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 1.5], gap="large")

    with left:
        st.markdown("#### 📋 Timeline")
        timeline_container = st.empty()

    with right:
        st.markdown("#### 📊 รายงาน")
        report_area = st.empty()
        report_area.markdown(
            '<div class="report"><p>🔄 AI กำลังเลือกเครื่องมือและรวบรวมหลักฐาน...</p></div>',
            unsafe_allow_html=True,
        )

    timeline_items = []
    ICONS = {"step": "○", "search": "🔍", "tool": "⚙️", "result": "↳", "done": "✓"}

    def on_event(event):
        kind = event.get("kind", "note")
        text = event.get("text", "")

        if kind in ("search", "tool"):
            icon = ICONS.get(kind, "○")
            timeline_items.append(
                f"""
            <div class="timeline-item">
                <div class="timeline-icon loading">{icon}</div>
                <div>
                    <div class="timeline-title">{html.escape(text)}</div>
                </div>
            </div>
            """
            )
        elif kind == "result":
            if timeline_items:
                timeline_items[-1] = timeline_items[-1].replace("loading", "success").replace(
                    "○", "✓"
                )
        elif kind == "done":
            timeline_items.append(
                f"""
            <div class="timeline-item">
                <div class="timeline-icon success">✓</div>
                <div>
                    <div class="timeline-title">{html.escape(text)}</div>
                </div>
            </div>
            """
            )

        timeline_html = '<div class="timeline">' + "".join(timeline_items) + "</div>"
        timeline_container.markdown(timeline_html, unsafe_allow_html=True)

    try:
        import os

        if st.session_state.get("saved_maxplus_key"):
            os.environ["MAXPLUS_API_KEY"] = st.session_state["saved_maxplus_key"]
        if st.session_state.get("saved_maxplus_base"):
            os.environ["MAXPLUS_BASE_URL"] = st.session_state["saved_maxplus_base"]
        if st.session_state.get("saved_maxplus_model"):
            os.environ["MAXPLUS_MODEL"] = st.session_state["saved_maxplus_model"]
        if st.session_state.get("saved_anthropic_key"):
            os.environ["ANTHROPIC_API_KEY"] = st.session_state["saved_anthropic_key"]
        trusted = [part.strip() for part in trusted_raw.split(",") if part.strip()]
        store = RunStore()
        orchestrator = Orchestrator(store)

        run_id = orchestrator.start(value, profile, trusted)
        thread = threading.Thread(target=orchestrator.run, args=(run_id,), daemon=True)
        thread.start()

        cursor = 0
        while thread.is_alive():
            for event in store.list_events(run_id, cursor):
                cursor = event["seq"]
                kind = event["kind"]
                if kind in ("tool", "result", "candidate", "budget", "error", "report"):
                    icon = "⚙️" if kind == "tool" else "✓" if kind == "report" else "↳"
                    timeline_items.append(
                        f'<div class="timeline-item"><div class="timeline-icon success">{icon}</div>'
                        f'<div><div class="timeline-title">{html.escape(event["text"][:240])}</div></div></div>'
                    )
                    timeline_container.markdown(
                        '<div class="timeline">' + "".join(timeline_items) + "</div>",
                        unsafe_allow_html=True,
                    )
            time.sleep(0.3)
        thread.join()

        payload = store.to_dict(run_id) or {}
        report = payload.get("report") or "ไม่สามารถสร้างรายงานได้"
        findings = payload.get("findings") or []
        candidates = payload.get("candidates") or []
        analysis = analysis_view.build(store, run_id)

        report_area.markdown(
            f'<div class="report">{report}</div>', unsafe_allow_html=True
        )

        st.markdown("---")
        (
            tab_who, tab_ids, tab_profiles, tab_6d, tab_rel, tab_time,
            tab_report, tab_actions, tab_evidence, tab_candidates, tab_graph, tab_export,
        ) = st.tabs([
            "🧭 บุคคลนี้คือใคร", "🔎 ตัวระบุที่พบ", "👤 โปรไฟล์", "🧠 6D",
            "🕸️ ความสัมพันธ์", "🕒 Timeline", "📄 รายงาน", "🤖 Agent actions",
            "🧾 หลักฐาน", "👥 Candidates", "🕸️ ผัง", "💾 ส่งออก",
        ])

        def pivot_button(identifier, kind, key):
            if st.button("วิเคราะห์ต่อ", key=key):
                child = orchestrator.start(identifier, "deep", parent_run_id=run_id)
                threading.Thread(target=orchestrator.run, args=(child,), daemon=True).start()
                st.success(f"สร้าง run ต่อเนื่อง: {child}")

        with tab_who:
            narr = analysis.get("narrative") or {}
            st.markdown(narr.get("identity_answer", {}).get("narrative", "ยังไม่สามารถระบุได้"))
            for key, title in (
                ("digital_identity", "อัตลักษณ์ดิจิทัล"),
                ("work_education", "อาชีพ/การศึกษา/องค์กร"),
                ("geo_temporal", "พื้นที่และเวลา"),
                ("family", "ครอบครัว/บุคคลแวดล้อม"),
                ("lifestyle", "ความสนใจ"),
            ):
                st.markdown(f"**{title}**")
                st.markdown(narr.get(key, {}).get("narrative", "ยังไม่พบข้อมูล"))
            st.markdown("**6D**")
            for key, label in (("identity","Identity"),("geo_temporal","Geo-temporal"),
                               ("psychological","Psychological/OCEAN"),("technical","Technical"),
                               ("ideological","Ideological"),("opsec","OpSec")):
                item = (narr.get("six_d") or {}).get(key, {})
                st.markdown(f"- **{label}** ({item.get('confidence','Unverified')}): {item.get('narrative','ประเมินไม่ได้')}")
            st.caption("ย่อหน้าทั้งหมดอ้าง evidence id ที่ตรวจสอบได้; ดูรายละเอียดในแท็บหลักฐาน")

        with tab_ids:
            if analysis["names"]:
                st.markdown("**ชื่อที่พบ**")
                for index, name in enumerate(analysis["names"]):
                    st.markdown(
                        f"- {name['full_name']} (ชื่อ: {name['given_name']}, นามสกุล: {name['family_name']}) "
                        f"· {name['confidence']} · [source]({name['source_url']})"
                    )
                    if name.get("family_name"):
                        pivot_button(name["family_name"], "family_name", f"fam-{index}")
            if not analysis["identifiers"]:
                st.info("ยังไม่พบตัวระบุ")
            for index, item in enumerate(analysis["identifiers"][:60]):
                st.markdown(
                    f"**{item['type']}** `{item['value']}` · พบ {item['occurrences']} แหล่ง · {item['confidence']}"
                )
                if item["source_urls"]:
                    st.markdown(" · ".join(f"[source]({url})" for url in item["source_urls"][:3]))
                if item["next_pivots"]:
                    st.caption("แนะนำ: " + ", ".join(item["next_pivots"]))
                pivot_button(item["value"], item["type"], f"pivot-{index}")
                st.divider()

        with tab_profiles:
            if not analysis["profiles"]:
                st.info("ยังไม่พบโปรไฟล์ที่เปิดอ่าน")
            for profile in analysis["profiles"]:
                st.markdown(f"### {profile['platform']} · `{profile['username']}` · {profile['confidence']}")
                st.markdown(f"[{profile['url']}]({profile['url']})")
                for label, key in (("ชื่อ", "display_names"), ("bio", "bios"), ("สถานที่", "locations"),
                                   ("องค์กร", "organizations"), ("อีเมล", "emails"), ("เว็บ", "links")):
                    values = profile.get(key) or []
                    if values:
                        st.markdown(f"- **{label}**: {', '.join(str(v) for v in values[:4])}")
                st.caption("evidence: " + ", ".join(profile["evidence"]))
                st.divider()

        with tab_6d:
            for key, label in (("identity","Identity"),("geo_temporal","Geo-temporal"),
                               ("psychological","Psychological/OCEAN"),("technical","Technical"),
                               ("ideological","Ideological"),("opsec","OpSec")):
                item = analysis["cognitive"].get(key, {})
                st.markdown(f"### {label} — {item.get('confidence')}")
                st.markdown(item.get("assessment", "ประเมินไม่ได้"))
                if item.get("rationale"):
                    st.caption(item["rationale"])
                if item.get("metrics"):
                    st.code(str(item["metrics"]))

        with tab_rel:
            if analysis["explicit_relations"]:
                st.markdown("**ความสัมพันธ์ที่แหล่งระบุ**")
                for rel in analysis["explicit_relations"]:
                    st.markdown(
                        f"- **{rel.get('relationship')}**: {rel.get('name')} — {rel.get('snippet', '')[:160]}"
                    )
                    if rel.get("source_url"):
                        st.markdown(f"  [source]({rel['source_url']})")
            if not analysis["relationships"] and not analysis["explicit_relations"]:
                st.info("ยังไม่พบความสัมพันธ์ที่มีหลักฐาน")
            if analysis["relationships"]:
                st.caption("สัญญาณเชื่อมโยงจาก co-occurrence (ยังไม่ใช่คำระบุความสัมพันธ์)")
            for rel in analysis["relationships"]:
                st.markdown(f"- {rel['name']} ↔ {rel['handle']} (พบร่วม {rel['strength']})")

        with tab_time:
            if not analysis["timeline"]:
                st.info("ยังไม่พบวันที่")
            for event in analysis["timeline"]:
                st.markdown(f"- {event['date']} · {event['title']} · {event['platform']}")

        with tab_report:
            st.markdown(report, unsafe_allow_html=True)

        with tab_actions:
            action_findings = [f for f in findings if f["tool"].startswith("agent:")]
            if not action_findings:
                st.info("run นี้ใช้ deterministic plan (ไม่มี API key หรือ profile quick)")
            for finding in action_findings:
                st.markdown(f"**{finding['tool']}**")
                st.code(finding["output"][:1500])

        with tab_evidence:
            for finding in findings:
                st.markdown(
                    f"**{finding['tool']}** · `{finding['status']}` · "
                    f"`{finding.get('output_hash', '')[:23]}…`"
                )
                st.code(finding["output"][:2000] or "-")
                st.divider()

        with tab_candidates:
            if not candidates:
                st.info("ไม่พบ identity candidate")
            for candidate in candidates:
                st.markdown(
                    f"`{candidate['candidate_id']}` · **{candidate['status']}** · "
                    f"{', '.join(candidate.get('entity_ids', []))}"
                )
                cols = st.columns(3)
                for label, action in (("ยืนยัน", "confirm"), ("ตัด", "reject"), ("ย้อน", "reverse")):
                    if cols[0 if action == "confirm" else 1 if action == "reject" else 2].button(
                        label, key=f"{candidate['candidate_id']}-{action}"
                    ):
                        store.decide_candidate(run_id, candidate["candidate_id"], action)
                        st.rerun()

        with tab_graph:
            with st.spinner("กำลังสร้างผังความสัมพันธ์…"):
                graph = build_relationship_graph(_build_client(), report)
                graph_html = build_graph_html(graph)
            if graph_html:
                st.components.v1.html(graph_html, height=560, scrolling=False)
            else:
                st.info("รายงานนี้ยังไม่มีความสัมพันธ์ที่ยืนยันได้")

        with tab_export:
            col1, col2 = st.columns(2)
            with col1:
                html_export = build_report_html(report, identifier_type, value, context)
                st.download_button(
                    "📥 ดาวน์โหลด HTML",
                    html_export,
                    file_name=f"report_{value[:20]}.html",
                    mime="text/html",
                    use_container_width=True,
                )
            with col2:
                st.download_button(
                    "📥 ดาวน์โหลด Markdown",
                    report,
                    file_name=f"report_{value[:20]}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

    except Exception as exc:
        st.error(f"เกิดข้อผิดพลาด: {exc}")
