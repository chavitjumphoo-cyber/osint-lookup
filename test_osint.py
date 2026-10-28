"""
Test script for OSINT Agent
ทดสอบการค้นหาข้อมูลด้วย username จริง
"""

import sys
import os
import json

# Fix encoding for Windows console
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors='replace')
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, errors='replace')

from osint_agent.agent import run_osint_lookup

def print_event(event):
    """แสดงผล event แบบ real-time"""
    kind = event.get("kind", "")
    text = event.get("text", "")

    if kind == "tool":
        print(f"[Tool] {text}")
    elif kind == "search":
        print(f"[Search] {text}")
    elif kind == "note":
        print(f"[Note] {text}")
    elif kind == "result":
        print(f"[Result] {text}")
    elif kind == "done":
        print(f"[Done] {text}")
    else:
        print(f"[Log] {text}")

def test_username_search():
    """ทดสอบค้นหา username ที่รู้จักว่ามีข้อมูล"""

    # ทดสอบด้วย username ที่น่าจะหาเจอ (GitHub founder)
    username = "torvalds"  # Linus Torvalds (Linux creator)

    print("=" * 60)
    print(f"Testing OSINT Lookup: {username}")
    print("=" * 60)
    print()

    try:
        report = run_osint_lookup(
            identifier_type="username",
            identifier_value=username,
            context="Test: Find information about this username",
            api_keys={},
            on_event=print_event
        )

        print("\n" + "=" * 60)
        print("FINAL REPORT")
        print("=" * 60)
        print(report)

        return True

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_username_search()
    sys.exit(0 if success else 1)
