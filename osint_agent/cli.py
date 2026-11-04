"""CLI — scan / agent / resume / export / review / doctor"""

import argparse
import json
import sys
import time

from .agent import read_config
from .services.orchestrator import Orchestrator, RunNotFound
from .services.store import RunStore

REQUIRED_MODULES = [
    ("anthropic", "เรียก Claude/MaxPlus"),
    ("requests", "HTTP พื้นฐาน"),
    ("bs4", "อ่าน HTML"),
    ("phonenumbers", "ตรวจเบอร์"),
    ("httpx", "platform scanner"),
    ("PIL", "เปรียบเทียบรูป"),
    ("googlesearch", "web_search fallback"),
    ("ddgs", "web_search fallback"),
    ("pyvis", "ผังความสัมพันธ์"),
    ("fastapi", "REST API"),
]

OPTIONAL_BINARIES = [("sherlock", "sherlock_username")]


def _check_modules() -> list[str]:
    import importlib

    problems = []
    for module, purpose in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"ขาด {module} ({purpose}): {type(exc).__name__}")
    return problems


def _check_tools() -> list[str]:
    from .tools import TOOLS
    from .tools.registry import _module

    problems = []
    for name in TOOLS:
        try:
            _module(name)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"tool '{name}' import ไม่ได้: {type(exc).__name__}: {exc}")
    return problems


def _check_browser() -> tuple[list[str], list[str]]:
    from .services import browser

    if browser.available():
        return [], [f"moli: {browser.resolve_binary()}"]
    return ["ไม่พบ moli — fetch จะ fallback เป็น requests (คุณภาพต่ำกว่า)"], [
        "ติดตั้ง Moli: ./scripts/install-moli.sh หรือ python -m osint_agent.cli doctor --install-moli"
    ]


def _check_binaries() -> list[str]:
    import shutil

    return [
        f"ไม่พบคำสั่ง '{exe}' ใน PATH — {tool} จะใช้ไม่ได้"
        for exe, tool in OPTIONAL_BINARIES
        if not shutil.which(exe)
    ]


def _check_config() -> tuple[list[str], list[str]]:
    config = read_config()
    problems, notes = [], []
    if not config.get("ANTHROPIC_API_KEY") and not config.get("ANTHROPIC_BASE_URL"):
        problems.append("ไม่มี ANTHROPIC_API_KEY หรือ ANTHROPIC_BASE_URL ใน .env")
    else:
        notes.append("พบค่า LLM ใน .env")
    if not config.get("HIBP_API_KEY"):
        notes.append("ไม่มี HIBP_API_KEY — breach_check จะปิดอยู่")
    return problems, notes


def doctor() -> int:
    if sys.version_info < (3, 11):  # noqa: UP036 — doctor ต้องเตือนruntime
        problems = [f"ต้องใช้ Python 3.11 ขึ้นไป (พบ {sys.version.split()[0]})"]
    else:
        problems = []

    config_problems, notes = _check_config()
    browser_problems, browser_notes = _check_browser()
    problems += _check_modules() + _check_tools() + config_problems + browser_problems
    notes += browser_notes
    binary_problems = _check_binaries()

    print("== OSINT Lookup doctor ==")
    print(f"Python: {sys.version.split()[0]}")
    for note in notes:
        print(f"  note: {note}")
    for note in binary_problems:
        print(f"  warn: {note}")
    print()

    if problems:
        print(f"พบปัญหา {len(problems)} รายการ:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("ทุกอย่างพร้อมใช้งาน")
    return 0


def _follow(store: RunStore, run_id: str, start: int = 0) -> None:
    cursor = start
    while True:
        for event in store.list_events(run_id, cursor):
            cursor = event["seq"]
            print(f"[{event['kind']}] {event['text']}")
        run = store.get_run(run_id)
        if not run or run["status"] in {"done", "failed", "cancelled"}:
            return
        time.sleep(0.3)


def _execute(store: RunStore, target: str, profile: str, trusted: list[str] | None = None) -> int:
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start(target, profile, trusted)
    print(f"run: {run_id}")
    orchestrator.run(run_id)
    _follow(store, run_id)
    run = store.get_run(run_id)
    print(f"\nสถานะ: {run['status']}")
    for finding in store.list_findings(run_id):
        print(f"\n[{finding['tool']}]\n{finding['output']}")
    return 0 if run["status"] == "done" else 1


def cmd_scan(args, store: RunStore) -> int:
    return _execute(store, args.target, args.profile, args.trust)


def cmd_agent(args, store: RunStore) -> int:
    return _execute(store, args.target, "standard", args.trust)


def cmd_resume(args, store: RunStore) -> int:
    orchestrator = Orchestrator(store)
    try:
        result = orchestrator.run(args.run_id)
    except RunNotFound:
        print(f"ไม่พบ run {args.run_id}", file=sys.stderr)
        return 1
    for finding in result.findings:
        print(f"[{finding['tool']}]\n{finding['output']}\n")
    print(f"สถานะ: {result.status}")
    return 0 if result.status == "done" else 1


def cmd_export(args, store: RunStore) -> int:
    payload = store.to_dict(args.run_id)
    if not payload:
        print(f"ไม่พบ run {args.run_id}", file=sys.stderr)
        return 1
    if args.research:
        from .profiling import profile_resolver, research_report

        artifacts = store.list_artifacts(args.run_id)
        entities = profile_resolver.extract_entities(artifacts)
        profiles = profile_resolver.resolve_profiles(artifacts, entities)
        markdown = research_report.build_markdown(
            payload, artifacts, store.list_findings(args.run_id), profiles, entities
        )
        if args.docx:
            target = args.output or f"research_{args.run_id}.docx"
            research_report.to_docx(markdown, target)
            print(f"เขียนแล้ว: {target}")
            return 0
        text = markdown
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"เขียนแล้ว: {args.output}")
    else:
        print(text)
    return 0


def cmd_review(args, store: RunStore) -> int:
    payload = store.to_dict(args.run_id)
    if not payload:
        print(f"ไม่พบ run {args.run_id}", file=sys.stderr)
        return 1
    print(f"run {args.run_id} · {payload['target_type']} = {payload['target']} · {payload['status']}")
    if args.candidate:
        if not args.action:
            print("ต้องระบุ --action ด้วย", file=sys.stderr)
            return 1
        decided = store.decide_candidate(args.run_id, args.candidate, args.action)
        if not decided:
            print("ไม่พบ candidate", file=sys.stderr)
            return 1
        print(f"{decided['candidate_id']}: {decided['status']}")
        return 0
    for candidate in payload["candidates"]:
        print(f"candidate {candidate['candidate_id']} · {candidate['status']} · {candidate['entity_ids']}")
    for finding in payload["findings"]:
        print(f"\n#{finding['seq']} [{finding['tool']}] {finding['created_at']}\n{finding['output']}")
    if payload.get("report"):
        print("\n--- report ---\n" + payload["report"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="osint", description="OSINT Lookup CLI")
    parser.add_argument("--db", default=None, help="path ของ SQLite run store")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_parser = sub.add_parser("doctor", help="ตรวจความพร้อมของสภาพแวดล้อม")
    doctor_parser.add_argument("--install-moli", action="store_true", help="ติดตั้ง Moli แล้วตรวจ")

    scan = sub.add_parser("scan", help="สแกนเป้าหมายและแสดงผลทันที")
    scan.add_argument("target")
    scan.add_argument(
        "--profile", "-p", choices=["quick", "standard", "deep"], default="quick"
    )
    scan.add_argument("--trust", action="append", default=[], help="network:user หรือ email:addr")

    agent = sub.add_parser("agent", help="รันแบบ standard profile")
    agent.add_argument("target")
    agent.add_argument("--trust", action="append", default=[], help="network:user หรือ email:addr")

    resume = sub.add_parser("resume", help="ทำ run เดิมต่อจาก checkpoint")
    resume.add_argument("run_id")

    export = sub.add_parser("export", help="ส่งออก run เป็น JSON")
    export.add_argument("run_id")
    export.add_argument("--output", "-o")
    export.add_argument("--research", action="store_true", help="ออกรายงานวิจัยจาก run")
    export.add_argument("--docx", action="store_true", help="ออกรายงานวิจัยเป็น .docx")

    review = sub.add_parser("review", help="แสดงหลักฐาน/candidate และตัดสินได้")
    review.add_argument("run_id")
    review.add_argument("--candidate")
    review.add_argument("--action", choices=["confirm", "reject", "reverse"])

    args = parser.parse_args(argv)
    if args.command == "doctor":
        if args.install_moli:
            import subprocess

            subprocess.run(["bash", "scripts/install-moli.sh"], check=False)
        return doctor()

    if args.db:
        import os

        os.environ["OSINT_DB"] = args.db
    store = RunStore()
    handlers = {
        "scan": cmd_scan,
        "agent": cmd_agent,
        "resume": cmd_resume,
        "export": cmd_export,
        "review": cmd_review,
    }
    return handlers[args.command](args, store)


if __name__ == "__main__":
    raise SystemExit(main())
