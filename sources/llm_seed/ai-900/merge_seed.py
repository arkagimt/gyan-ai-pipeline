#!/usr/bin/env python3
"""
AI-900 seed merger
==================
Reads raw batch JSON from stdin (or a file argument), flattens MCQs + notes
into the canonical seed format, and writes ai-900-v1.json.

Output artifact:
  ai-900-v1.json     — 100 MCQs + 10 notes + meta + known_issues

Usage:
  python merge_seed.py raw_batches.json
  # or pipe:  cat raw_batches.json | python merge_seed.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE     = Path(__file__).resolve().parent
OUT_PATH = HERE / "ai-900-v1.json"

# Domain ordering (matches the official AI-900 skills outline)
DOMAIN_ORDER = [
    "Describe Artificial Intelligence workloads and considerations",
    "Describe fundamental principles of machine learning on Azure",
    "Describe features of computer vision workloads on Azure",
    "Describe features of Natural Language Processing (NLP) workloads on Azure",
    "Describe features of generative AI workloads on Azure",
]

# Batch label → domain mapping
BATCH_TO_DOMAIN = {
    "A": DOMAIN_ORDER[0],
    "B": DOMAIN_ORDER[1],
    "C": DOMAIN_ORDER[2],
    "D": DOMAIN_ORDER[3],
    "E": DOMAIN_ORDER[4],
}


def main() -> int:
    # Read input
    if len(sys.argv) > 1:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    data = json.loads(raw)
    batches = data["batches"]

    all_mcqs: list[dict] = []
    all_notes: list[dict] = []
    seq = 1

    for batch in batches:
        for mcq in batch["mcqs"]:
            mcq_out = {
                "seq": seq,
                "question": mcq["question"],
                "options": mcq["options"],
                "correct": mcq["correct"],
                "reasoning_process": mcq["reasoning_process"],
                "explanation": mcq["explanation"],
                "difficulty": mcq["difficulty"],
                "bloom_level": mcq["bloom_level"],
                "topic_tag": mcq["topic_tag"],
            }
            all_mcqs.append(mcq_out)
            seq += 1

        for note in batch["notes"]:
            all_notes.append({
                "topic_title": note["topic_title"],
                "summary": note["summary"],
                "key_concepts": note["key_concepts"],
                "formulas": note.get("formulas", []),
                "important_facts": note["important_facts"],
                "examples": note.get("examples", []),
                "memory_hooks": note.get("memory_hooks", []),
            })

    # Build meta
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

    OUT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ Wrote {len(all_mcqs)} MCQs + {len(all_notes)} notes → {OUT_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
