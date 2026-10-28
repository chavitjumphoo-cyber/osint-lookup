"""
Simple OSINT Test - Test with a well-known username
"""

import sys
import os

# Fix encoding
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors='replace')
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, errors='replace')

from osint_agent.agent import run_osint_lookup

# Test with a well-known username
username = "torvalds"  # Linus Torvalds

print("=" * 60)
print(f"Testing OSINT Agent with username: {username}")
print("=" * 60)
print()

events = []

def collect_event(event):
    """Collect events"""
    events.append(event)
    kind = event.get("kind", "")
    text = event.get("text", "")[:100]
    print(f"[{kind}] {text}")

try:
    print("Starting investigation...")
    report = run_osint_lookup(
        identifier_type="username",
        identifier_value=username,
        context="Find all available information",
        api_keys={},
        on_event=collect_event
    )

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(report)
    print("\n" + "=" * 60)
    print(f"Total events: {len(events)}")

except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
