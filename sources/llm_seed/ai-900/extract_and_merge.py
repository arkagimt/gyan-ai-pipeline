#!/usr/bin/env python3
"""
Extract AI-900 batch JSON from the Antigravity conversation log,
merge into canonical seed format, write ai-900-v1.json.
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT  = HERE / "ai-900-v1.json"
LOG  = Path(r"C:\Users\arkag\.gemini\antigravity\brain\e13c8e32-3e13-4c43-9829-b409cfc12f1c\.system_generated\logs\overview.txt")

def find_batches_json(text: str) -> dict:
    """Find the { "batches":[ ... ] } blob in the log text."""
    # Find the start marker
    idx = text.find('{ "batches":[')
    if idx == -1:
        raise ValueError("Could not find batches JSON in log")
    
    # Find matching closing brace by counting braces
    depth = 0
    start = idx
    for i in range(idx, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                raw = text[start:i+1]
                return json.loads(raw)
    raise ValueError("Unbalanced braces in JSON blob")

def main():
    print(f"Reading conversation log: {LOG}")
    log_text = LOG.read_text(encoding="utf-8", errors="replace")
    print(f"  Log size: {len(log_text):,} chars")
    
    data = find_batches_json(log_text)
    batches = data["batches"]
    print(f"  Found {len(batches)} batches")
    
    all_mcqs = []
    all_notes = []
    seq = 1
    
    for b in batches:
        label = b.get("batch", "?")
        n_mcq = len(b["mcqs"])
        n_note = len(b["notes"])
        print(f"  Batch {label}: {n_mcq} MCQs, {n_note} notes")
        
        for mcq in b["mcqs"]:
            all_mcqs.append({
                "seq": seq,
                "question": mcq["question"],
                "options": mcq["options"],
                "correct": mcq["correct"],
                "reasoning_process": mcq["reasoning_process"],
                "explanation": mcq["explanation"],
                "difficulty": mcq["difficulty"],
                "bloom_level": mcq["bloom_level"],
                "topic_tag": mcq["topic_tag"],
            })
            seq += 1
        
        for note in b["notes"]:
            all_notes.append({
                "topic_title": note["topic_title"],
                "summary": note["summary"],
                "key_concepts": note["key_concepts"],
                "formulas": note.get("formulas", []),
                "important_facts": note["important_facts"],
                "examples": note.get("examples", []),
                "memory_hooks": note.get("memory_hooks", []),
            })
    
    artifact = {
        "meta": {
            "schema_version": "1.0",
            "source_type": "llm_knowledge",
            "generator": "gemini-2.5-pro (Google AI Studio)",
            "human_reviewed": False,
            "syllabus_revision": "2025-05",
            "pipeline_ingest": {
                "exam": "ai-900",
                "provider": "Microsoft",
                "authority": "microsoft",
                "segment": "it",
            },
            "stats": {
                "total_mcqs": len(all_mcqs),
                "total_notes": len(all_notes),
                "difficulty_split": {
                    d: sum(1 for m in all_mcqs if m["difficulty"] == d)
                    for d in ("easy", "medium", "hard")
                },
                "bloom_split": {
                    b: sum(1 for m in all_mcqs if m["bloom_level"] == b)
                    for b in ("remember", "understand", "apply", "analyze",
                              "evaluate", "create")
                },
            },
            "known_issues": [],
            "audit_gate": {
                "status": "pending",
                "audited_at": None,
                "pass_rate": None,
            },
        },
        "mcqs": all_mcqs,
        "notes": all_notes,
    }
    
    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Wrote {len(all_mcqs)} MCQs + {len(all_notes)} notes → {OUT.name}")
    
    # Quick self-audit
    diffs = artifact["meta"]["stats"]["difficulty_split"]
    blooms = artifact["meta"]["stats"]["bloom_split"]
    print(f"   Difficulty: {diffs}")
    print(f"   Bloom:      {blooms}")
    
    # Validate seq contiguity
    seqs = [m["seq"] for m in all_mcqs]
    expected = list(range(1, len(all_mcqs) + 1))
    assert seqs == expected, f"Seq not contiguous: got {seqs[:5]}...{seqs[-5:]}"
    print("   Seq: contiguous 1..100 ✓")

if __name__ == "__main__":
    main()
