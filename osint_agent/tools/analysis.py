"""เครื่องมือวิเคราะห์: platform scan, avatar, stylometry และ identity correlation"""

import json

from .base import plain


def scan_platforms_schema():
    return {
        "name": "scan_platforms",
        "description": (
            "สแกน username ข้าม 30+ แพลตฟอร์มพร้อมกัน — เร็วกว่า sherlock และ real-time\n\n"
            "ผลลัพธ์จำแนกเป็น พบ / ไม่พบ / ตรวจไม่ได้ / ยังสรุปไม่ได้ "
            "(สถานะ 'ยังสรุปไม่ได้' คือแพลตฟอร์มที่ตอบ 200 ทุกชื่อ ต้องเปิดดูเองด้วย fetch_page)\n\n"
            "ใช้เมื่อต้องการค้นหา username แบบครอบคลุม"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username ที่ต้องการสแกน เช่น johndoe, testuser123",
                },
            },
            "required": ["username"],
        },
    }


def run_scan_platforms(username: str) -> dict:
    from .. import platform_scanner

    try:
        results = platform_scanner.scan_sync(username)
        return plain(platform_scanner.format_scan_results(results))
    except Exception as exc:  # noqa: BLE001
        return plain(f"เกิดข้อผิดพลาด: {str(exc)}")


def compare_avatars_schema():
    return {
        "name": "compare_avatars",
        "description": (
            "เปรียบเทียบ 2 รูปโปรไฟล์ด้วย perceptual dHash — ตรวจจับว่าเป็นรูปเดียวกันหรือไม่ "
            "แม้จะ resize/recompress/crop เล็กน้อย ใช้ระบุว่าบัญชีหลายบัญชีเป็นคนเดียวกัน"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "avatar_url_1": {"type": "string", "description": "URL รูปที่ 1 (หรือ path ในเครื่อง)"},
                "avatar_url_2": {"type": "string", "description": "URL รูปที่ 2 (หรือ path ในเครื่อง)"},
            },
            "required": ["avatar_url_1", "avatar_url_2"],
        },
    }


def run_compare_avatars(url1: str, url2: str) -> dict:
    from .. import advanced_tools

    try:
        result = advanced_tools.compare_avatars(url1, url2)
        if result.get("error"):
            return plain(f"ข้อผิดพลาด: {result['error']}")

        lines = ["🖼️ เปรียบเทียบรูปโปรไฟล์"]
        lines.append(f"รูปที่ 1: {url1}")
        lines.append(f"รูปที่ 2: {url2}")
        lines.append("")
        lines.append(f"ผลลัพธ์: {'✅ ตรงกัน (รูปเดียวกัน)' if result['matched'] else '❌ ไม่ตรงกัน'}")
        lines.append(f"ความคล้าย: {result['similarity_percentage']}%")
        lines.append(f"Hamming distance: {result['hamming_distance']} bits")
        lines.append(f"Hash 1: {result['hash1']}")
        lines.append(f"Hash 2: {result['hash2']}")
        return plain("\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        return plain(f"เกิดข้อผิดพลาด: {type(exc).__name__}: {exc}")


def correlate_stylometry_schema():
    return {
        "name": "correlate_stylometry",
        "description": (
            "วิเคราะห์ลายมือเขียน (stylometry) ด้วย character n-gram — เทียบว่า 2 ข้อความ "
            "เขียนโดยคนเดียวกันหรือไม่ ใช้ระบุบัญชีนิรนามหลายบัญชีที่เป็นคนเดียวกัน "
            "ข้อความต้องยาวอย่างน้อย 40 ตัวอักษร"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text1": {"type": "string", "description": "ข้อความที่ 1 (เช่น โพสต์/คอมเมนต์จากบัญชีที่รู้จัก)"},
                "text2": {"type": "string", "description": "ข้อความที่ 2 (เช่น โพสต์/คอมเมนต์จากบัญชีนิรนาม)"},
            },
            "required": ["text1", "text2"],
        },
    }


def run_correlate_stylometry(text1: str, text2: str) -> dict:
    from .. import advanced_tools

    result = advanced_tools.correlate_stylometry(text1, text2)

    lines = ["✍️ การวิเคราะห์ลายมือเขียน (Stylometry)"]
    if result.get("warning"):
        lines.append(f"⚠️ {result['warning']}")
    else:
        lines.append(f"ความคล้าย: {result['similarity']:.2%}")
        lines.append(f"ประเมิน: {result['interpretation']}")
        lines.append("")
        lines.append("คำแนะนำการแปลผล:")
        lines.append("- > 0.85: เขียนโดยคนเดียวกันมาก")
        lines.append("- 0.70-0.85: เขียนโดยคนเดียวกันได้")
        lines.append("- 0.50-0.70: คล้ายกันปานกลาง")
        lines.append("- < 0.50: แตกต่างกัน")

    return plain("\n".join(lines))


def username_correlation_schema():
    return {
        "name": "username_correlation",
        "description": (
            "สร้าง username variants และหาความเชื่อมโยงใน corpus ที่เก็บมา — "
            "จาก username หนึ่งสร้าง variants หลายรูปแบบ (john.doe → johndoe, j.doe, jdoe) "
            "แล้วเช็คว่ามีปรากฏในข้อความที่เก็บมาหรือไม่"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username seed (เช่น john.doe, @johndoe, https://twitter.com/johndoe)",
                },
                "collected_text": {
                    "type": "string",
                    "description": "ข้อความทั้งหมดที่เก็บมาจาก web_search, fetch_page, sherlock",
                },
            },
            "required": ["username", "collected_text"],
        },
    }


def run_username_correlation(username: str, collected_text: str) -> dict:
    from .. import synint_agents

    result = synint_agents.username_correlation_agent(username, collected_text)

    lines = ["🔗 Username Correlation Analysis"]
    lines.append(f"Seed: {result['seed']}")
    lines.append(f"Generated variants: {len(result['generated_variants'])} รูปแบบ")
    lines.append(f"Matched variants: {len(result['matched_variants'])} รูปแบบ")
    lines.append(f"Confidence: {result['confidence_score']:.0%}")
    lines.append("")

    if result["matched_variants"]:
        lines.append("✅ พบ variants เหล่านี้ใน corpus:")
        for variant in result["matched_variants"][:10]:
            lines.append(f"- {variant}")
        if len(result["matched_variants"]) > 10:
            lines.append(f"... และอีก {len(result['matched_variants']) - 10} รูปแบบ")
    else:
        lines.append("❌ ไม่พบ variants ใน corpus")

    if result["clusters"]:
        lines.append("")
        lines.append("🔍 Reuse Clusters:")
        for cluster in result["clusters"]:
            lines.append(f"- {cluster['cluster_id']}: {len(cluster['variants'])} variants")

    lines.append("")
    lines.append("⚠️ หมายเหตุ:")
    for note in result["confidence_notes"]:
        lines.append(f"- {note}")

    return plain("\n".join(lines))


def email_harvest_schema():
    return {
        "name": "email_harvest",
        "description": (
            "สร้างรูปแบบอีเมลที่เป็นไปได้จากโดเมน — สร้าง role accounts (admin@, info@, support@) "
            "และ person patterns (first.last@, flast@) เป็น hypothesis เท่านั้น ไม่ได้ยืนยันว่ามีจริง"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "โดเมน (เช่น example.com)"},
                "first_name": {"type": "string", "description": "ชื่อตัวอย่าง (ถ้ารู้จัก) — default: john"},
                "last_name": {"type": "string", "description": "นามสกุลตัวอย่าง (ถ้ารู้จัก) — default: doe"},
            },
            "required": ["domain"],
        },
    }


def run_email_harvest(domain: str, first_name: str = "john", last_name: str = "doe") -> dict:
    from .. import synint_agents

    result = synint_agents.email_harvest_agent(domain, first_name, last_name)

    role_words = ("admin", "info", "support", "sales", "security", "contact")
    lines = ["📧 Email Pattern Generation"]
    lines.append(f"Domain: {result['domain']}")
    lines.append(f"Generated: {result['generated_count']} addresses")
    lines.append("")
    lines.append("🎯 Role Accounts:")
    for addr in result["generated_addresses"][:12]:
        if any(role in addr for role in role_words):
            lines.append(f"- {addr}")
    lines.append("")
    lines.append("👤 Person Patterns:")
    for addr in result["generated_addresses"][:12]:
        if not any(role in addr for role in role_words):
            lines.append(f"- {addr}")

    lines.append("")
    lines.append(f"⚠️ {result['confidence_note']}")
    return plain("\n".join(lines))


def identity_candidate_schema():
    return {
        "name": "identity_candidate",
        "description": (
            "วิเคราะห์ identity candidates — หาว่า entities หลายตัวเป็นคนเดียวกันหรือไม่ "
            "จับคู่ตาม email, username, phone ที่ตรงกัน ต้องมี human reviewer ยืนยัน"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entities_json": {
                    "type": "string",
                    "description": 'JSON array ของ entities เช่น [{"name":"John","email":"j@ex.com"},{"name":"J.Doe","email":"j@ex.com"}]',
                },
            },
            "required": ["entities_json"],
        },
    }


def run_identity_candidate(entities_json: str) -> dict:
    from .. import synint_agents

    try:
        entities = json.loads(entities_json)
    except json.JSONDecodeError:
        return plain("❌ entities_json ไม่ใช่ JSON ที่ถูกต้อง")

    if not isinstance(entities, list):
        return plain("❌ entities_json ต้องเป็น array")

    result = synint_agents.identity_candidate_agent(entities)

    lines = ["🔍 Identity Candidate Analysis"]
    lines.append(f"Input entities: {len(entities)}")
    lines.append(f"Candidates found: {result['candidate_count']}")
    lines.append("")

    if result.get("reason"):
        lines.append(f"⚠️ {result['reason']}")
    elif result["identity_candidates"]:
        lines.append("🎯 Identity Matches:")
        for candidate in result["identity_candidates"]:
            lines.append(f"\n- Match Type: {candidate['match_type']}")
            lines.append(f"  Signal: {candidate['signal']}")
            lines.append(f"  Entities: {', '.join(candidate['entities'])}")
            lines.append(f"  Confidence: {candidate['confidence']}")
            lines.append(f"  Sources: {candidate['source_count']}")

        lines.append("")
        lines.append(f"⚠️ {result['confirmation_policy']}")

    return plain("\n".join(lines))


def darkweb_monitor_schema():
    return {
        "name": "darkweb_monitor",
        "description": (
            "Dark web monitoring scaffold — เตรียม hooks สำหรับค้นข้อมูลรั่วไหล "
            "คำนวณ entropy และระบุ matching patterns (ยังไม่ได้ integrate กับ breach database จริง)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Email, username, หรือ domain ที่ต้องการค้น"},
            },
            "required": ["target"],
        },
    }


def run_darkweb_monitor(target: str) -> dict:
    from .. import synint_agents

    result = synint_agents.darkweb_monitor_agent(target)

    lines = ["🕵️ Dark Web Monitor (Scaffold)"]
    lines.append(f"Target: {result['search_target']}")
    lines.append(f"Entropy: {result['target_entropy']}")
    lines.append(f"Classification: {result['agent_classification']}")
    lines.append("")
    lines.append("📚 Supported Local Sources:")
    for source in result["local_sources_supported"]:
        lines.append(f"- {source}")
    lines.append("")
    lines.append("🔍 Matching Hooks:")
    for hook, enabled in result["matching_hooks"].items():
        lines.append(f"{'✅' if enabled else '❌'} {hook}")
    lines.append("")
    lines.append(f"⚠️ {result['note']}")
    return plain("\n".join(lines))
