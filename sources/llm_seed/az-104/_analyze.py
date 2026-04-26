"""
AZ-104 Critical Analysis — same thorough checks as DP-900.
1. Parse structure
2. MCQ schema validation
3. Notes quality
4. Internal duplicate detection
5. Summary
"""
import json, sys, os, re
from difflib import SequenceMatcher
sys.stdout.reconfigure(encoding="utf-8")

FILE = r"C:\Users\arkag\.gemini\antigravity\playground\sparse-halo\jsonformatter_az104.txt"

# ── Parse multi-object file ─────────────────────────────────────────
text = open(FILE, "r", encoding="utf-8").read()
cleaned = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
cleaned = re.sub(r"  +", " ", cleaned)
print(f"Raw file: {len(cleaned):,} chars")

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
            try:
                objects.append(json.loads(cleaned[start:i+1]))
            except json.JSONDecodeError as e:
                print(f"  Parse error at {start}: {e}")
            start = None

print(f"Parsed {len(objects)} JSON objects")

batches = [o for o in objects if "batch" in o]
audits = [o for o in objects if "self_audit" in o]
print(f"  Batches: {len(batches)}, Self-audits: {len(audits)}")

mcqs = []
notes = []
for b in batches:
    label = b.get("batch", "?")
    m = b.get("mcqs", [])
    n = b.get("notes", [])
    print(f"  Batch {label}: {len(m)} MCQs, {len(n)} notes — {b.get('domain','')[:50]}")
    mcqs.extend(m)
    notes.extend(n)

print(f"\nTotal: {len(mcqs)} MCQs, {len(notes)} notes")

if audits:
    sa = audits[0].get("self_audit", {})
    print(f"Self-audit: target={sa.get('target_mcq_count')}, actual={sa.get('actual_mcq_count')}")

# ── MCQ Schema Validation ────────────────────────────────────────────
print(f"\n{'='*70}")
print("  MCQ SCHEMA VALIDATION")
print("="*70)

if mcqs:
    print(f"  MCQ[0] keys: {sorted(mcqs[0].keys())}")

valid_correct = {"A", "B", "C", "D"}
valid_diff = {"easy", "medium", "hard"}
valid_bloom = {"remember", "understand", "apply", "analyze", "evaluate", "create"}

issues = []
for i, mcq in enumerate(mcqs):
    idx = i + 1
    c = mcq.get("correct", mcq.get("correct_answer", ""))
    if c not in valid_correct:
        issues.append(f"MCQ {idx}: correct={c!r}")
    d = (mcq.get("difficulty", "") or "").lower()
    if d and d not in valid_diff:
        issues.append(f"MCQ {idx}: difficulty={d!r}")
    b = (mcq.get("bloom_level", mcq.get("bloom", "")) or "").lower()
    if b and b not in valid_bloom:
        issues.append(f"MCQ {idx}: bloom={b!r}")
    opts = mcq.get("options", {})
    if isinstance(opts, dict) and not all(k in opts for k in "ABCD"):
        issues.append(f"MCQ {idx}: missing option keys")
    if not mcq.get("question"):
        issues.append(f"MCQ {idx}: empty question")
    if not mcq.get("reasoning_process") and not mcq.get("rationale"):
        issues.append(f"MCQ {idx}: no reasoning_process")
    if not mcq.get("explanation"):
        issues.append(f"MCQ {idx}: no explanation")
    if not mcq.get("topic_tag"):
        issues.append(f"MCQ {idx}: no topic_tag")

if issues:
    print(f"  ⚠ {len(issues)} issues:")
    for iss in issues[:20]:
        print(f"    - {iss}")
    if len(issues) > 20:
        print(f"    ... and {len(issues)-20} more")
else:
    print("  ✓ All MCQs pass schema validation")

# Distributions
diffs = {}
blooms = {}
for mcq in mcqs:
    d = (mcq.get("difficulty", "") or "").lower()
    b = (mcq.get("bloom_level", mcq.get("bloom", "")) or "").lower()
    diffs[d] = diffs.get(d, 0) + 1
    blooms[b] = blooms.get(b, 0) + 1
print(f"  Difficulty: {dict(sorted(diffs.items()))}")
print(f"  Bloom:      {dict(sorted(blooms.items()))}")

tags = {}
for mcq in mcqs:
    t = mcq.get("topic_tag", "")
    tags[t] = tags.get(t, 0) + 1
print(f"  Topic tags ({len(tags)}):")
for t in sorted(tags.keys()):
    print(f"    [{tags[t]:2d}] {t}")

# ── Notes Quality ─────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  NOTES QUALITY")
print("="*70)
if notes:
    print(f"  Note[0] keys: {sorted(notes[0].keys())}")
for i, n in enumerate(notes):
    title = n.get("topic_title", n.get("topic", f"Note {i+1}"))
    kc = len(n.get("key_concepts", []))
    fi = len(n.get("important_facts", []))
    ex = len(n.get("examples", []))
    mh = len(n.get("memory_hooks", []))
    sm = len(n.get("summary", ""))
    status = "✓" if kc >= 3 and fi >= 2 else "⚠"
    print(f"  [{i+1:2d}] {status} {title[:55]}")
    print(f"       summary:{sm} concepts:{kc} facts:{fi} examples:{ex} hooks:{mh}")

# ── Internal Duplicate Detection ──────────────────────────────────────
print(f"\n{'='*70}")
print("  INTERNAL DUPLICATE DETECTION")
print("="*70)

def norm(t):
    return re.sub(r"\s+", " ", t.lower().strip())

qs = [(i, norm(m["question"])) for i, m in enumerate(mcqs)]
dupes = []
for i in range(len(qs)):
    for j in range(i+1, len(qs)):
        r = SequenceMatcher(None, qs[i][1], qs[j][1]).ratio()
        if r > 0.70:
            dupes.append((i+1, j+1, r, mcqs[i]["question"][:60]))

if dupes:
    print(f"  ⚠ {len(dupes)} potential duplicates:")
    for a, b, r, q in dupes:
        print(f"    MCQ {a} ↔ MCQ {b} ({r:.0%}): {q}...")
else:
    print("  ✓ No internal duplicates found")

# ── Summary ───────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  VERDICT")
print("="*70)
print(f"  MCQs: {len(mcqs)} | Notes: {len(notes)}")
print(f"  Schema issues: {len(issues)}")
print(f"  Internal dupes: {len(dupes)}")
thin = sum(1 for n in notes if len(n.get("key_concepts",[])) < 3)
print(f"  Thin notes: {thin}/{len(notes)}")
total = len(issues) + len(dupes)
if total == 0 and thin == 0:
    print("\n  ✅ READY TO PROCEED")
elif total == 0:
    print(f"\n  ⚠ PROCEED WITH CAUTION — {thin} thin notes")
else:
    print(f"\n  ❌ {total} issues to address")
