import json, sys, re
sys.stdout.reconfigure(encoding="utf-8")

RAW = "sources/llm_seed/ai-900/_raw_batches.json"

with open(RAW, "r", encoding="utf-8") as f:
    text = f.read()

print(f"Raw file: {len(text):,} chars")

# Fix: replace literal control chars (newlines/tabs inside JSON strings)
# First try strict parse
try:
    d = json.loads(text)
    print("Parsed OK (strict)")
except json.JSONDecodeError as e:
    print(f"Strict parse failed at char {e.pos}: {e.msg}")
    print(f"  Near: ...{repr(text[max(0,e.pos-30):e.pos+30])}...")
    
    # Try with control char cleanup
    # Replace literal newlines/tabs that are inside JSON string values
    cleaned = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
    # Also replace tabs
    cleaned = cleaned.replace('\t', ' ')
    # Collapse multiple spaces
    cleaned = re.sub(r'  +', ' ', cleaned)
    
    try:
        d = json.loads(cleaned)
        print("Parsed OK (after cleanup)")
    except json.JSONDecodeError as e2:
        print(f"Cleanup parse also failed at char {e2.pos}: {e2.msg}")
        print(f"  Near: ...{repr(cleaned[max(0,e2.pos-50):e2.pos+50])}...")
        sys.exit(1)

batches = d.get("batches", [])
print(f"{len(batches)} batches found")
total_mcqs = 0
total_notes = 0
for b in batches:
    nm = len(b["mcqs"])
    nn = len(b["notes"])
    total_mcqs += nm
    total_notes += nn
    print(f"  Batch {b['batch']}: {nm} MCQs, {nn} notes")
print(f"Total: {total_mcqs} MCQs, {total_notes} notes")

# Rewrite formatted
with open(RAW, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print("Reformatted and saved!")
