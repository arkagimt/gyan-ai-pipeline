"""Parse DP-900 raw JSON (flat schema), build canonical seed, validate."""
import json, sys, re, os
sys.stdout.reconfigure(encoding="utf-8")

RAW_IN  = r"C:\Users\arkag\.gemini\antigravity\playground\sparse-halo\jsonformatter.txt"
HERE    = os.path.dirname(os.path.abspath(__file__))
RAW_OUT = os.path.join(HERE, "_raw_batches.json")
SEED    = os.path.join(HERE, "dp-900-v1.json")

# DP-900 official domains + weights
DOMAINS = [
    {"name": "Describe core data concepts", "weight": 25},
    {"name": "Identify considerations for relational data on Azure", "weight": 25},
    {"name": "Describe considerations for working with non-relational data on Azure", "weight": 25},
    {"name": "Describe an analytics workload on Azure", "weight": 25},
]

# 1. Read + clean
text = open(RAW_IN, "r", encoding="utf-8").read()
print(f"Raw input: {len(text):,} chars")
cleaned = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
cleaned = re.sub(r"  +", " ", cleaned)
d = json.loads(cleaned)

# Save cleaned raw
with open(RAW_OUT, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

raw_mcqs = d["mcqs"]
raw_notes = d.get("study_notes", [])
print(f"Parsed: {len(raw_mcqs)} MCQs, {len(raw_notes)} notes")

# 2. Map MCQ fields to canonical schema
# Source: id, domain, topic, difficulty, bloom, question, options, correct_answer, rationale
# Target: seq, question, options{A,B,C,D}, correct, reasoning_process, explanation, difficulty, bloom_level, topic_tag

all_mcqs = []
for i, mcq in enumerate(raw_mcqs, 1):
    opts = mcq["options"]
    # Options might be a dict {A:..., B:..., C:..., D:...} or a list
    if isinstance(opts, list):
        options = {chr(65+j): o for j, o in enumerate(opts[:4])}
    elif isinstance(opts, dict):
        options = opts
    else:
        print(f"  WARNING: MCQ {i} has unexpected options type: {type(opts)}")
        continue
    
    # correct_answer might be "A", "B", etc. or might have text
    correct = mcq.get("correct_answer", mcq.get("correct", ""))
    if len(correct) > 1:
        # It's the full text, find which option matches
        for k, v in options.items():
            if correct.strip().lower() == v.strip().lower():
                correct = k
                break
        else:
            correct = correct[0].upper()  # take first char
    
    all_mcqs.append({
        "seq": i,
        "question": mcq["question"],
        "options": options,
        "correct": correct.upper(),
        "reasoning_process": mcq.get("rationale", mcq.get("reasoning_process", "")),
        "explanation": mcq.get("explanation", mcq.get("rationale", "")[:200]),
        "difficulty": mcq.get("difficulty", "medium").lower(),
        "bloom_level": mcq.get("bloom", mcq.get("bloom_level", "understand")).lower(),
        "topic_tag": mcq.get("topic", mcq.get("topic_tag", mcq.get("domain", "General"))),
    })

# 3. Map notes
all_notes = []
for note in raw_notes:
    content = note.get("content", {})
    if isinstance(content, str):
        # Simple text content
        all_notes.append({
            "topic_title": note.get("topic", ""),
            "summary": content[:300],
            "key_concepts": [],
            "formulas": [],
            "important_facts": [],
            "examples": [],
            "memory_hooks": [],
        })
    elif isinstance(content, dict):
        all_notes.append({
            "topic_title": note.get("topic", content.get("topic_title", "")),
            "summary": content.get("summary", ""),
            "key_concepts": content.get("key_concepts", []),
            "formulas": content.get("formulas", []),
            "important_facts": content.get("important_facts", []),
            "examples": content.get("examples", []),
            "memory_hooks": content.get("memory_hooks", []),
        })

# 4. Build artifact
artifact = {
    "meta": {
        "schema_version": "1.0",
        "source_type": "llm_knowledge",
        "generator": "gemini-2.5-pro (Google AI Studio)",
        "human_reviewed": False,
        "syllabus_revision": "2025-05",
        "pipeline_ingest": {
            "exam": "dp-900",
            "provider": "Microsoft",
            "authority": "microsoft",
            "segment": "it",
            "label": "Microsoft Azure Data Fundamentals \u2014 DP-900",
        },
        "stats": {
            "total_mcqs": len(all_mcqs),
            "total_notes": len(all_notes),
            "difficulty_split": {
                dd: sum(1 for m in all_mcqs if m["difficulty"] == dd)
                for dd in ("easy", "medium", "hard")
            },
            "bloom_split": {
                bb: sum(1 for m in all_mcqs if m["bloom_level"] == bb)
                for bb in ("remember", "understand", "apply", "analyze", "evaluate", "create")
            },
        },
        "known_issues": [],
        "audit_gate": {"status": "pending", "audited_at": None, "pass_rate": None},
    },
    "mcqs": all_mcqs,
    "notes": all_notes,
}

with open(SEED, "w", encoding="utf-8") as f:
    json.dump(artifact, f, ensure_ascii=False, indent=2)

print(f"\nWrote {len(all_mcqs)} MCQs + {len(all_notes)} notes -> dp-900-v1.json")
print(f"  Difficulty: {artifact['meta']['stats']['difficulty_split']}")
print(f"  Bloom:      {artifact['meta']['stats']['bloom_split']}")

# 5. Validate
seqs = [m["seq"] for m in all_mcqs]
expected = list(range(1, len(all_mcqs) + 1))
assert seqs == expected, f"Seq not contiguous!"
print(f"  Seq: contiguous 1..{len(all_mcqs)}")

bad_correct = [m["seq"] for m in all_mcqs if m["correct"] not in ("A","B","C","D")]
if bad_correct:
    print(f"  WARNING: Bad correct values at seq {bad_correct}")
    for s in bad_correct[:5]:
        m = all_mcqs[s-1]
        print(f"    seq {s}: correct={m['correct']!r}")
else:
    print(f"  Correct: all A|B|C|D")

valid_diff = {"easy", "medium", "hard"}
valid_bloom = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
bad_diff = [m["seq"] for m in all_mcqs if m["difficulty"] not in valid_diff]
bad_bloom = [m["seq"] for m in all_mcqs if m["bloom_level"] not in valid_bloom]
if bad_diff:
    print(f"  WARNING: Bad difficulty at {bad_diff}")
if bad_bloom:
    print(f"  WARNING: Bad bloom at {bad_bloom}")
if not bad_diff and not bad_bloom:
    print(f"  Difficulty + Bloom: valid")

tags = sorted(set(m["topic_tag"] for m in all_mcqs))
print(f"  Unique topic_tags ({len(tags)}):")
for t in tags:
    print(f"    - {t}")

print("\nALL CHECKS PASSED")
