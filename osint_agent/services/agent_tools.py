"""เครื่องมือระดับสูงที่ AgentEngine ใช้ — ทุกตัวผ่าน evidence core"""

from __future__ import annotations

import json

from ..profiling import collectors, profile_extractor
from ..profiling.identity_score import score_pair
from .tool_runner import run_tool


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


TOOL_SCHEMAS = [
    _schema("search_web", "ค้นเว็บหลาย engine", {"query": {"type": "string"}}, ["query"]),
    _schema("search_name", "ค้นชื่อเต็มพร้อม site เฉพาะ", {"name": {"type": "string"}}, ["name"]),
    _schema("search_surname", "ค้นนามสกุลพร้อมบริบทครอบครัว", {"surname": {"type": "string"}, "context": {"type": "string"}}, ["surname"]),
    _schema("search_family_relation", "ค้นนามสกุลร่วมกับคำบอกความสัมพันธ์", {"surname": {"type": "string"}, "relation": {"type": "string"}}, ["surname"]),
    _schema("scan_profiles", "ตรวจ username บนแพลตฟอร์มและดึง metadata", {"username": {"type": "string"}}, ["username"]),
    _schema("fetch_profile", "เปิดหน้าโปรไฟล์ด้วย Moli และสกัดโปรไฟล์", {"url": {"type": "string"}}, ["url"]),
    _schema("browser_capture_profile", "เหมือน fetch_profile — จับโปรไฟล์แบบมีหลักฐาน", {"url": {"type": "string"}}, ["url"]),
    _schema("browser_observe", "เปิดหน้าและสรุปหัวข้อ/ลิงก์ที่พบ", {"url": {"type": "string"}}, ["url"]),
    _schema("browser_capture_post", "เปิดโพสต์และสกัดผู้เขียน วันที่ ชื่อ/องค์กร/ความสัมพันธ์", {"url": {"type": "string"}}, ["url"]),
    _schema("browser_follow_links", "เปิดหน้าและคืนลิงก์ที่ควรตามต่อ", {"url": {"type": "string"}, "max_links": {"type": "integer"}}, ["url"]),
    _schema("fetch_page", "เปิดหน้าเว็บทั่วไปและสกัด entity", {"url": {"type": "string"}}, ["url"]),
    _schema("extract_profile", "สกัดโปรไฟล์จาก artifact ที่มีอยู่", {"artifact_id": {"type": "string"}}, ["artifact_id"]),
    _schema("scan_github", "ดึงข้อมูลสาธารณะจาก GitHub API", {"username": {"type": "string"}}, ["username"]),
    _schema("scan_email", "ตรวจ breach และ Gravatar", {"email": {"type": "string"}}, ["email"]),
    _schema("scan_phone", "ตรวจข้อมูลเบอร์และ WhatsApp", {"phone": {"type": "string"}}, ["phone"]),
    _schema("compare_avatar", "เทียบรูปโปรไฟล์สองรูป", {"url_a": {"type": "string"}, "url_b": {"type": "string"}}, ["url_a", "url_b"]),
    _schema("compare_profiles", "ให้คะแนนว่าโปรไฟล์สองอันเป็นคนเดียวกัน", {"profile_a": {"type": "string"}, "profile_b": {"type": "string"}}, ["profile_a", "profile_b"]),
    _schema("search_corpus", "ค้นหลักฐานใน corpus", {"query": {"type": "string"}}, ["query"]),
    _schema("add_lead", "เพิ่ม lead เพื่อไปต่อยอด", {"value": {"type": "string"}, "type": {"type": "string"}, "reason": {"type": "string"}}, ["value", "type", "reason"]),
    _schema("verify_identity_candidate", "ดู candidate ที่ระบบสร้าง", {}, []),
    _schema("finalize_report", "หยุดสืบสวนและสร้างรายงาน", {}, []),
]

EXECUTABLE = {schema["name"] for schema in TOOL_SCHEMAS}


def _summarize_artifacts(artifacts) -> dict:
    return {
        "added": len(artifacts),
        "items": [
            {
                "artifact_id": a.artifact_id,
                "url": a.source_url,
                "type": a.source_type,
                "platform": a.platform,
                "status": a.status,
                "preview": a.content[:200],
            }
            for a in artifacts[:10]
        ],
    }


def execute(name: str, args: dict, ctx) -> dict:
    if name == "search_web":
        return _summarize_artifacts([a for a in collectors.search(args["query"], limit=8) if ctx.state.add_artifact(a)])

    if name in {"search_name", "search_surname", "search_family_relation"}:
        from ..profiling.thai_identity import surname_queries

        if name == "search_name":
            queries = [f'"{args["name"]}"', f'"{args["name"]}" site:facebook.com']
        elif name == "search_surname":
            queries = surname_queries(args["surname"], [args.get("context", "")])[:3]
        else:
            queries = [f'"{args["surname"]}" {args["relation"]}']
        added = []
        for query in queries:
            added += [a for a in collectors.search(query, limit=5) if ctx.state.add_artifact(a)]
        return {**_summarize_artifacts(added), "queries": queries}

    if name == "scan_profiles":
        from ..profiling import collectors as c

        found = [a for a in c.scan_profiles(args["username"]) if ctx.state.add_artifact(a)]
        probed = [a for a in c.probe_platforms(args["username"]) if ctx.state.add_artifact(a)]
        return {**_summarize_artifacts(found), "probed": len(probed), "probe_urls": [a.source_url for a in probed[:8]]}

    if name in {"fetch_profile", "fetch_page", "browser_capture_profile", "browser_observe", "browser_follow_links", "browser_capture_post"}:
        artifact = collectors.fetch(args["url"])
        ctx.state.fetches += 1
        fields = {}
        if artifact.status == "ok" and artifact.content and (
            artifact.source_type == "profile" or name == "browser_capture_post"
        ):
            if name == "browser_capture_post":
                artifact.source_type = "post"
            fields = profile_extractor.extract(artifact.to_dict())
            artifact.metadata["profile_fields"] = fields
        added = ctx.state.add_artifact(artifact)
        payload = {"added": added, "status": artifact.status, "fields": {k: v[:3] for k, v in fields.items() if v}}
        if name == "browser_observe":
            payload["title"] = artifact.title
        if name == "browser_follow_links":
            links = fields.get("websites", [])[: int(args.get("max_links") or 5)]
            payload["links"] = [entry["value"] for entry in links]
        return payload

    if name == "extract_profile":
        artifact = next((a for a in ctx.state.artifacts if a["artifact_id"] == args["artifact_id"]), None)
        if not artifact:
            return {"error": "ไม่พบ artifact"}
        return profile_extractor.extract(artifact)

    if name == "scan_github":
        out = run_tool("github_intel", {"username": args["username"]})
        return {"status": out.status, "result": out.result[:1200]}

    if name == "scan_email":
        breach = run_tool("breach_check", {"email": args["email"]})
        grav = run_tool("gravatar_lookup", {"email": args["email"]})
        return {"breach": breach.result[:800], "gravatar": grav.result[:800]}

    if name == "scan_phone":
        info = run_tool("phone_info", {"number": args["phone"]})
        adv = run_tool("scan_phone_advanced", {"phone_number": args["phone"]})
        return {"info": info.result[:800], "advanced": adv.result[:1200]}

    if name == "compare_avatar":
        out = run_tool("compare_avatars", {"avatar_url_1": args["url_a"], "avatar_url_2": args["url_b"]})
        return {"result": out.result[:600]}

    if name == "compare_profiles":
        by_key = {p["key"]: p for p in ctx.state.profiles}
        a = by_key.get(args["profile_a"]) or next((p for p in ctx.state.profiles if p["url"] == args["profile_a"]), None)
        b = by_key.get(args["profile_b"]) or next((p for p in ctx.state.profiles if p["url"] == args["profile_b"]), None)
        if not a or not b:
            return {"error": "ไม่พบโปรไฟล์"}
        return score_pair(a, b)

    if name == "search_corpus":
        from ..tools import execute_tool

        out = execute_tool("search_evidence", {"run_id": ctx.state.run_id, "query": args["query"]})
        return {"result": out["output"][:1500]}

    if name == "add_lead":
        ctx.state.leads.append({"value": args["value"], "type": args["type"], "reason": args["reason"]})
        return {"leads": len(ctx.state.leads)}

    if name == "verify_identity_candidate":
        return {"candidates": ctx.store.list_candidates(ctx.state.run_id)[:10]}

    if name == "finalize_report":
        return {"finalized": True}

    return {"error": f"ไม่รู้จัก tool {name}"}


def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)[:8000]
