"""
Full OSINT Test - Test with real username
"""

import sys
import os

# Fix encoding
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors='replace')

from osint_agent.agent import run_osint_lookup

# Test with a well-known username
username = "torvalds"  # Linus Torvalds

print("=" * 60)
print(f"OSINT Agent Test: {username}")
print("=" * 60)
print()

def show_event(event):
    """Show progress"""
    kind = event.get("kind", "")
    text = event.get("text", "")

    if kind == "thinking":
        print(f"[AI Thinking] {text[:100]}")
    elif kind == "tool":
        print(f"[Tool Call] {text}")
    elif kind == "result":
        print(f"[Result] {text[:150]}")
    elif text:
        print(f"[{kind}] {text[:100]}")

try:
    print("Starting investigation...\n")

    report = run_osint_lookup(
        identifier_type="username",
        identifier_value=username,
        context="Find comprehensive information about this username",
        api_keys={},
        on_event=show_event
    )

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(report)

except KeyboardInterrupt:
    print("\n\nTest interrupted by user")
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
