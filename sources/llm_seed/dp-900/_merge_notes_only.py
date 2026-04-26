"""
Option A: Merge ONLY the 11 structured notes from the updated file
into the existing dp-900-v1.json seed. MCQs stay untouched.
"""
import json, sys, re
sys.stdout.reconfigure(encoding="utf-8")

NEW_FILE = r"C:\Users\arkag\.gemini\antigravity\playground\sparse-halo\jsonformatter_updated_dp900.txt"
SEED     = "sources/llm_seed/dp-900/dp-900-v1.json"

# 1. Parse multi-object file
text = open(NEW_FILE, "r", encoding="utf-8").read()
cleaned = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
cleaned = re.sub(r"  +", " ", cleaned)

depth = 0
objects = []
start = None
for i, ch in enumerate(cleaned):
    if ch == '{':
        if depth == 0: start = i
        depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0 and start is not None:
            objects.append(json.loads(cleaned[start:i+1]))
            start = None

batches = [o for o in objects if "batch" in o]
new_notes = []
for b in batches:
    new_notes.extend(b.get("notes", []))

print(f"Extracted {len(new_notes)} structured notes from updated file")

# 2. Validate notes quality
for i, n in enumerate(new_notes):
    kc = len(n.get("key_concepts", []))
    fi = len(n.get("important_facts", []))
    ex = len(n.get("examples", []))
    mh = len(n.get("memory_hooks", []))
    sm = len(n.get("summary", ""))
    print(f"  [{i+1:2d}] {n['topic_title'][:50]}")
    print(f"       summary:{sm} concepts:{kc} facts:{fi} examples:{ex} hooks:{mh}")

# 3. Load existing seed, replace ONLY notes
seed = json.load(open(SEED, "r", encoding="utf-8"))
old_notes_count = len(seed["notes"])
print(f"\nExisting seed: {len(seed['mcqs'])} MCQs, {old_notes_count} notes (replacing notes only)")

seed["notes"] = new_notes
seed["meta"]["stats"]["total_notes"] = len(new_notes)

# 4. Save
with open(SEED, "w", encoding="utf-8") as f:
    json.dump(seed, f, ensure_ascii=False, indent=2)

print(f"\nMerged: {len(seed['mcqs'])} MCQs (unchanged) + {len(new_notes)} notes (NEW structured)")
print("dp-900-v1.json updated successfully")
