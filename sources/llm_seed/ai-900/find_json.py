#!/usr/bin/env python3
"""Find and extract the batches JSON from the conversation log."""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

LOG = r"C:\Users\arkag\.gemini\antigravity\brain\e13c8e32-3e13-4c43-9829-b409cfc12f1c\.system_generated\logs\overview.txt"
OUT = os.path.join(os.path.dirname(__file__), "_raw_batches.json")

text = open(LOG, "r", encoding="utf-8", errors="replace").read()
print(f"Log size: {len(text):,} chars")

# The user's message contains the JSON inline. Search for the pattern.
# Try multiple patterns
patterns = [
    '{ "batches":[',
    '{"batches":[',
    '"batches":[',
    '"batches": [',
]

for pat in patterns:
    idx = text.find(pat)
    if idx >= 0:
        print(f"Found pattern {pat!r} at index {idx}")
        # Back up to find the opening brace if needed
        if pat.startswith('"'):
            # find preceding {
            for j in range(idx-1, max(0, idx-50), -1):
                if text[j] == '{':
                    idx = j
                    break
        
        # Now find matching closing brace
        depth = 0
        for i in range(idx, min(len(text), idx + 200000)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    raw = text[idx:i+1]
                    print(f"Extracted {len(raw):,} chars")
                    try:
                        data = json.loads(raw)
                        print(f"Parsed OK! Batches: {len(data.get('batches', []))}")
                        with open(OUT, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"Wrote {OUT}")
                        sys.exit(0)
                    except json.JSONDecodeError as e:
                        print(f"JSON parse failed: {e}")
                        # Try to show around error
                        pos = e.pos or 0
                        print(f"Near: ...{raw[max(0,pos-40):pos+40]}...")
                        break
        break
else:
    print("No pattern found!")
    # Show some samples of text around likely areas
    for kw in ["batches", "EXAM CARD", "Describe Artificial"]:
        idx = text.find(kw)
        if idx >= 0:
            snippet = text[max(0,idx-20):idx+100].replace('\n', '\\n')
            print(f"  '{kw}' at {idx}: {snippet[:120]}")
