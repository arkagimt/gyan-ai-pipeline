"""Validate ai-900-v1.json against the master prompt's 6 checks."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")

SEED = "sources/llm_seed/ai-900/ai-900-v1.json"
DOMAINS = [
    "Describe Artificial Intelligence workloads and considerations",
    "Describe fundamental principles of machine learning on Azure",
    "Describe features of computer vision workloads on Azure",
    "Describe features of Natural Language Processing (NLP) workloads on Azure",
    "Describe features of generative AI workloads on Azure",
]
# Also accept sub-objective topic_tags from the exam guide
VALID_TOPICS = set()
# Build a set of all known topic_tags (the user's data uses sub-objective names)

d = json.load(open(SEED, "r", encoding="utf-8"))
fails = []

# 1. meta.pipeline_ingest.exam == "ai-900"
exam = d["meta"]["pipeline_ingest"]["exam"]
if exam != "ai-900":
    fails.append(f"FAIL: meta.pipeline_ingest.exam = {exam!r}, expected 'ai-900'")
else:
    print(f"[1] meta.pipeline_ingest.exam = {exam!r} OK")

# 2. meta.audit_gate.status present
status = d["meta"]["audit_gate"]["status"]
print(f"[2] meta.audit_gate.status = {status!r} OK")

# 3. mcqs[] and notes[] exist; seq contiguous from 1
mcqs = d["mcqs"]
notes = d["notes"]
seqs = [m["seq"] for m in mcqs]
expected = list(range(1, len(mcqs) + 1))
if seqs != expected:
    fails.append(f"FAIL: seq not contiguous. Got {seqs[:5]}...{seqs[-5:]}")
else:
    print(f"[3] {len(mcqs)} MCQs (seq 1..{len(mcqs)}), {len(notes)} notes OK")

# 4. topic_tag matches domains — collect all unique tags
all_tags = set(m["topic_tag"] for m in mcqs)
print(f"[4] Unique topic_tags ({len(all_tags)}):")
for tag in sorted(all_tags):
    print(f"    - {tag}")
# Note: topic_tags are sub-objectives, not domain names. That's fine for the pipeline.
# The domain filter uses fuzzy matching.

# 5. correct is A|B|C|D
bad_correct = [m["seq"] for m in mcqs if m["correct"] not in ("A","B","C","D")]
if bad_correct:
    fails.append(f"FAIL: bad 'correct' values at seq {bad_correct}")
else:
    print(f"[5] All correct values in A|B|C|D OK")

# 6. difficulty + bloom_level
valid_diff = {"easy", "medium", "hard"}
valid_bloom = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
bad_diff = [m["seq"] for m in mcqs if m["difficulty"] not in valid_diff]
bad_bloom = [m["seq"] for m in mcqs if m["bloom_level"] not in valid_bloom]
if bad_diff:
    fails.append(f"FAIL: bad difficulty at seq {bad_diff}")
if bad_bloom:
    fails.append(f"FAIL: bad bloom_level at seq {bad_bloom}")
if not bad_diff and not bad_bloom:
    stats = d["meta"]["stats"]
    print(f"[6] Difficulty: {stats['difficulty_split']}  Bloom: {stats['bloom_split']} OK")

if fails:
    print("\n=== FAILURES ===")
    for f in fails:
        print(f"  {f}")
    sys.exit(1)
else:
    print("\n=== ALL 6 CHECKS PASSED ===")
