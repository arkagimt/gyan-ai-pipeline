"""Compare notes quality between AZ-900, AI-900, and DP-900 seeds."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")

SEEDS = {
    "az-900": "sources/llm_seed/az-900/az-900-v1.json",
    "ai-900": "sources/llm_seed/ai-900/ai-900-v1.json",
    "dp-900": "sources/llm_seed/dp-900/dp-900-v1.json",
}

for slug, path in SEEDS.items():
    d = json.load(open(path, "r", encoding="utf-8"))
    notes = d["notes"]
    print(f"\n{'='*60}")
    print(f"  {slug.upper()} — {len(notes)} notes")
    print(f"{'='*60}")
    for i, n in enumerate(notes):
        kc = n.get("key_concepts", [])
        ff = n.get("formulas", [])
        fi = n.get("important_facts", [])
        ex = n.get("examples", [])
        mh = n.get("memory_hooks", [])
        summary_len = len(n.get("summary", ""))
        print(f"  [{i+1}] {n.get('topic_title', '???')[:60]}")
        print(f"      summary: {summary_len} chars | concepts: {len(kc)} | facts: {len(fi)} | examples: {len(ex)} | hooks: {len(mh)} | formulas: {len(ff)}")
        if summary_len < 20:
            print(f"      ⚠ THIN summary: {n.get('summary','')!r}")
        if not kc:
            print(f"      ⚠ EMPTY key_concepts")

# Also check the raw DP-900 content structure
print(f"\n{'='*60}")
print(f"  RAW DP-900 study_notes structure")
print(f"{'='*60}")
raw = json.load(open("sources/llm_seed/dp-900/_raw_batches.json", "r", encoding="utf-8"))
for i, n in enumerate(raw.get("study_notes", [])[:3]):
    print(f"\n  [{i+1}] Keys: {list(n.keys())}")
    content = n.get("content", {})
    print(f"      content type: {type(content).__name__}")
    if isinstance(content, dict):
        print(f"      content keys: {list(content.keys())}")
        for k, v in content.items():
            if isinstance(v, list):
                print(f"        {k}: list[{len(v)}] — {str(v[0])[:80] if v else 'empty'}...")
            elif isinstance(v, str):
                print(f"        {k}: str({len(v)} chars) — {v[:80]}...")
    elif isinstance(content, str):
        print(f"      content: {content[:120]}...")
