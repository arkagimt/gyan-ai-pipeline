"""
Critical analysis of updated DP-900 content — handles multi-object file.
"""
import json, sys, re
from difflib import SequenceMatcher
sys.stdout.reconfigure(encoding="utf-8")

NEW_FILE = r"C:\Users\arkag\.gemini\antigravity\playground\sparse-halo\jsonformatter_updated_dp900.txt"
OLD_SEED = r"sources/llm_seed/dp-900/dp-900-v1.json"

# ── Parse multi-object file ───────────────────────────────────────────
text = open(NEW_FILE, "r", encoding="utf-8").read()
cleaned = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
cleaned = re.sub(r"  +", " ", cleaned)

# Extract individual JSON objects
depth = 0
objects = []
start = None
for i, ch in enumerate(cleaned):
    if ch == '{':
        if depth == 0:
            start = i
        depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0 and start is not None:
            try:
                obj = json.loads(cleaned[start:i+1])
                objects.append(obj)
            except json.JSONDecodeError as e:
                print(f"  Parse error at object starting {start}: {e}")
            start = None

print(f"Parsed {len(objects)} JSON objects")

# Separate batches from self_audit
batches = [o for o in objects if "batch" in o]
audit = [o for o in objects if "self_audit" in o]

print(f"  Batches: {len(batches)}")
if audit:
    sa = audit[0]["self_audit"]
    print(f"  Self-audit: target={sa.get('target_mcq_count')}, actual={sa.get('actual_mcq_count')}")

# Collect all MCQs and notes
new_mcqs = []
new_notes = []
for b in batches:
    label = b.get("batch", "?")
    mcqs = b.get("mcqs", [])
    notes = b.get("notes", [])
    print(f"  Batch {label}: {len(mcqs)} MCQs, {len(notes)} notes — {b.get('domain','')[:50]}")
    new_mcqs.extend(mcqs)
    new_notes.extend(notes)

print(f"\nTotal: {len(new_mcqs)} MCQs, {len(new_notes)} notes")

# ── MCQ Schema Validation ─────────────────────────────────────────────
print(f"\n{'='*70}")
print("  MCQ SCHEMA VALIDATION")
print("="*70)

sample = new_mcqs[0] if new_mcqs else {}
print(f"  MCQ[0] keys: {sorted(sample.keys())}")

valid_correct = {"A", "B", "C", "D"}
valid_diff = {"easy", "medium", "hard"}
valid_bloom = {"remember", "understand", "apply", "analyze", "evaluate", "create"}

issues = []
for i, mcq in enumerate(new_mcqs):
    idx = i + 1
    # Correct
    c = mcq.get("correct", mcq.get("correct_answer", ""))
    if c not in valid_correct:
        issues.append(f"MCQ {idx}: correct={c!r}")
    # Difficulty
    d = (mcq.get("difficulty", "") or "").lower()
    if d and d not in valid_diff:
        issues.append(f"MCQ {idx}: difficulty={d!r}")
    # Bloom
    b = (mcq.get("bloom_level", mcq.get("bloom", "")) or "").lower()
    if b and b not in valid_bloom:
        issues.append(f"MCQ {idx}: bloom={b!r}")
    # Options
    opts = mcq.get("options", {})
    if isinstance(opts, dict) and not all(k in opts for k in "ABCD"):
        issues.append(f"MCQ {idx}: missing option keys")

if issues:
    print(f"  ⚠ {len(issues)} issues:")
    for iss in issues[:20]:
        print(f"    - {iss}")
else:
    print("  ✓ All MCQs pass schema validation")

# Distributions
diffs = {}
blooms = {}
for mcq in new_mcqs:
    d = (mcq.get("difficulty", "") or "").lower()
    b = (mcq.get("bloom_level", mcq.get("bloom", "")) or "").lower()
    diffs[d] = diffs.get(d, 0) + 1
    blooms[b] = blooms.get(b, 0) + 1
print(f"  Difficulty: {dict(sorted(diffs.items()))}")
print(f"  Bloom:      {dict(sorted(blooms.items()))}")

tags = {}
for mcq in new_mcqs:
    t = mcq.get("topic_tag", mcq.get("topic", ""))
    tags[t] = tags.get(t, 0) + 1
print(f"  Topic tags ({len(tags)}):")
for t in sorted(tags.keys()):
    print(f"    [{tags[t]:2d}] {t}")

# ── Notes Quality ─────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  NOTES QUALITY CHECK")
print("="*70)
print(f"  Note[0] keys: {sorted(new_notes[0].keys()) if new_notes else 'N/A'}")

for i, note in enumerate(new_notes):
    title = note.get("topic_title", note.get("topic", f"Note {i+1}"))
    kc = len(note.get("key_concepts", []))
    fi = len(note.get("important_facts", []))
    ex = len(note.get("examples", []))
    mh = len(note.get("memory_hooks", []))
    sm = len(note.get("summary", ""))
    status = "✓" if kc >= 3 and fi >= 2 and ex >= 1 and mh >= 1 else "⚠"
    print(f"  [{i+1:2d}] {status} {title[:50]}")
    print(f"       summary:{sm} concepts:{kc} facts:{fi} examples:{ex} hooks:{mh}")

# ── Internal Duplicate Detection ──────────────────────────────────────
print(f"\n{'='*70}")
print("  INTERNAL DUPLICATE DETECTION")
print("="*70)

def norm(text):
    return re.sub(r"\s+", " ", text.lower().strip())

qs = [(i, norm(m["question"])) for i, m in enumerate(new_mcqs)]
internal_dupes = []
for i in range(len(qs)):
    for j in range(i+1, len(qs)):
        r = SequenceMatcher(None, qs[i][1], qs[j][1]).ratio()
        if r > 0.70:
            internal_dupes.append((i+1, j+1, r, new_mcqs[i]["question"][:60]))

if internal_dupes:
    print(f"  ⚠ {len(internal_dupes)} potential duplicates (>70% similarity):")
    for a, b, r, q in internal_dupes:
        print(f"    MCQ {a} ↔ MCQ {b} ({r:.0%}): {q}...")
else:
    print("  ✓ No internal duplicates found")

# ── Cross-Duplicate Detection ─────────────────────────────────────────
print(f"\n{'='*70}")
print("  CROSS-DUPLICATE DETECTION (new vs existing seed)")
print("="*70)

try:
    old = json.load(open(OLD_SEED, "r", encoding="utf-8"))
    old_mcqs = old.get("mcqs", [])
    print(f"  Existing seed: {len(old_mcqs)} MCQs")

    old_qs = [norm(m["question"]) for m in old_mcqs]
    cross_dupes = []
    for i, mcq in enumerate(new_mcqs):
        nq = norm(mcq["question"])
        for j, oq in enumerate(old_qs):
            r = SequenceMatcher(None, nq, oq).ratio()
            if r > 0.65:
                cross_dupes.append((i+1, j+1, r, mcq["question"][:60]))

    if cross_dupes:
        print(f"  ⚠ {len(cross_dupes)} cross-duplicates (>65% similarity):")
        for ni, oi, r, q in sorted(cross_dupes, key=lambda x: -x[2]):
            print(f"    NEW #{ni} ↔ OLD #{oi} ({r:.0%}): {q}...")
    else:
        print("  ✓ No cross-duplicates — all new MCQs are unique vs existing seed")
except FileNotFoundError:
    print("  No existing seed — skipping")

# ── Final Summary ─────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  VERDICT")
print("="*70)
total_issues = len(issues) + len(internal_dupes) + (len(cross_dupes) if 'cross_dupes' in dir() else 0)
thin_notes = sum(1 for n in new_notes if len(n.get("key_concepts",[])) < 3)
print(f"  MCQs: {len(new_mcqs)} | Notes: {len(new_notes)}")
print(f"  Schema issues: {len(issues)}")
print(f"  Internal dupes: {len(internal_dupes)}")
print(f"  Cross dupes: {len(cross_dupes) if 'cross_dupes' in dir() else 'N/A'}")
print(f"  Thin notes: {thin_notes}/{len(new_notes)}")
if total_issues == 0 and thin_notes == 0:
    print("\n  ✅ READY TO PROCEED — clean data, no duplicates, rich notes")
elif total_issues == 0 and thin_notes > 0:
    print(f"\n  ⚠ PROCEED WITH CAUTION — {thin_notes} notes need enrichment")
else:
    print(f"\n  ❌ NEEDS FIXES — {total_issues} issues to resolve before proceeding")
