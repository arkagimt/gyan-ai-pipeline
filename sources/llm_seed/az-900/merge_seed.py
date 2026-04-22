#!/usr/bin/env python3
"""
AZ-900 seed merger
==================
Deterministic, idempotent consolidation of Gemini 2.5 Pro output into a
single ingestion-ready artifact.

Reads:
  raw-round-1.json   — Batches A / B / C (74 MCQs + 9 notes)
  raw-round-2.json   — Batches B-EXT / C-EXT / FIXES (32 MCQs + 6 notes)

Writes:
  az-900-v1.json     — 100 MCQs + 15 notes + meta + known_issues

Rules:
  1. Apply FIXES to their target MCQs (5 auto-match by stem substring,
     1 hard-coded because the rewrite diverged too far for substring
     matching — documented below).
  2. Flatten in domain order: A → B → B-EXT → C → C-EXT. Stable seq IDs
     1..100 assigned post-flatten.
  3. Auto-prefix the `explanation` field of any MCQ in the "beyond skills
     outline" list with a student-visible warning. Single source of truth
     is the BEYOND_OUTLINE_STEMS list below.
  4. Emit meta block with source_type="llm_knowledge" + pipeline_ingest
     hints + known_issues[] manifest.

This script is idempotent: running it twice produces byte-identical output.
No hand edits to raw-round-*.json are required or permitted.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R1_PATH = HERE / "raw-round-1.json"
R2_PATH = HERE / "raw-round-2.json"
OUT_PATH = HERE / "az-900-v1.json"

# ── FIX mapping ───────────────────────────────────────────────────────────────
# Five fixes auto-match by stem substring. One (FIX 3) needs a hard-coded
# target because Gemini rewrote the stem wholesale (ARM/declarative → Bicep/
# idempotency scenario). The hard-coded entry is (batch_name, index_in_batch).
HARD_CODED_FIX_TARGETS: dict[int, tuple[str, int]] = {
    3: ("C", 13),   # "ARM templates utilize a declarative approach..." → Bicep idempotency
}

# ── Beyond-outline MCQs ───────────────────────────────────────────────────────
# These test concepts that sit outside Microsoft's published AZ-900 skills
# outline (Sept 2024) but have been observed on real proctored exams.
# Identified by a distinctive stem substring (robust against reordering).
# Listed reason appears in meta.known_issues for the admin audit dashboard.
BEYOND_OUTLINE_STEMS: list[tuple[str, str]] = [
    (
        "used Azure Blueprints to package role assignments",
        "Azure Blueprints / Landing Zones — part of Cloud Adoption Framework, "
        "not listed in Sept-2024 skills outline but has appeared on real exams.",
    ),
]

WARNING_PREFIX = "⚠️ Beyond skills outline — may still appear on the real exam. "

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load(p: Path) -> list:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_by_substring(mcqs: list[dict], needle: str) -> int | None:
    """Return the index of the MCQ whose question contains `needle`, or None."""
    hits = [i for i, m in enumerate(mcqs) if needle in m["question"]]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise RuntimeError(f"Ambiguous match for needle {needle!r}: {len(hits)} hits")
    return None


def _apply_fixes(batches_by_name: dict[str, dict], fixes: list[dict]) -> list[str]:
    """Apply each fix to its target. Returns a list of human-readable log entries."""
    log: list[str] = []
    for fix_idx, fix in enumerate(fixes):
        # Strip batch-management keys if Gemini added any; ensure MCQItem-clean
        clean_fix = {k: v for k, v in fix.items() if k in (
            "question", "options", "correct", "reasoning_process",
            "explanation", "difficulty", "bloom_level", "topic_tag",
        )}

        # Preferred: hard-coded target
        if fix_idx in HARD_CODED_FIX_TARGETS:
            bname, bidx = HARD_CODED_FIX_TARGETS[fix_idx]
            orig = batches_by_name[bname]["mcqs"][bidx]["question"]
            batches_by_name[bname]["mcqs"][bidx] = clean_fix
            log.append(f"FIX[{fix_idx}] -> {bname}[{bidx}] (hard-coded)  orig: {orig[:60]}")
            continue

        # Substring auto-match across A / B / C (FIXES never target EXT batches)
        stem_head = fix["question"][:50]
        matched = False
        for bname in ("A", "B", "C"):
            mcqs = batches_by_name[bname]["mcqs"]
            idx = _find_by_substring(mcqs, stem_head)
            if idx is not None:
                orig = mcqs[idx]["question"]
                mcqs[idx] = clean_fix
                log.append(f"FIX[{fix_idx}] -> {bname}[{idx}] (auto-match)  stem: {stem_head[:50]}")
                matched = True
                break
        if not matched:
            raise RuntimeError(
                f"FIX[{fix_idx}] could not be matched to any R1 MCQ. "
                f"Stem: {fix['question'][:80]!r}. "
                f"Add a hard-coded target to HARD_CODED_FIX_TARGETS."
            )
    return log


def _apply_beyond_outline(flat_mcqs: list[dict]) -> list[dict]:
    """Prefix explanations of beyond-outline MCQs; return known_issues entries."""
    known_issues: list[dict] = []
    for needle, reason in BEYOND_OUTLINE_STEMS:
        matches = [
            (i, m) for i, m in enumerate(flat_mcqs)
            if needle in m["question"]
        ]
        if not matches:
            raise RuntimeError(f"Beyond-outline needle not found: {needle!r}")
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous beyond-outline needle {needle!r}: {len(matches)} hits")
        i, m = matches[0]
        if not m["explanation"].startswith(WARNING_PREFIX):
            m["explanation"] = WARNING_PREFIX + m["explanation"]
        known_issues.append({
            "seq":         i + 1,                     # 1-indexed
            "flag":        "beyond_outline",
            "topic_tag":   m["topic_tag"],
            "stem_head":   m["question"][:100],
            "reason":      reason,
        })
    return known_issues


def _count_by(mcqs: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in mcqs:
        v = str(m.get(key, "?"))
        counts[v] = counts.get(v, 0) + 1
    return counts


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    r1 = _load(R1_PATH)
    r2 = _load(R2_PATH)

    # Index by batch name for easy in-place mutation
    all_batches = {b["batch"]: b for b in (r1 + r2)}
    required = ["A", "B", "C", "B-EXT", "C-EXT", "FIXES"]
    missing = [n for n in required if n not in all_batches]
    if missing:
        print(f"ERROR: missing batches {missing}", file=sys.stderr)
        return 1

    # 1. Apply fixes to A / B / C
    fix_log = _apply_fixes(all_batches, all_batches["FIXES"]["mcqs"])
    for entry in fix_log:
        print(entry)

    # 2. Flatten in domain order
    order = ["A", "B", "B-EXT", "C", "C-EXT"]
    flat_mcqs: list[dict] = []
    flat_notes: list[dict] = []
    for name in order:
        flat_mcqs.extend(all_batches[name]["mcqs"])
        flat_notes.extend(all_batches[name].get("notes", []))

    if len(flat_mcqs) != 100:
        print(f"WARNING: expected 100 MCQs, got {len(flat_mcqs)}", file=sys.stderr)

    # 3. Apply beyond-outline warnings + build known_issues
    known_issues = _apply_beyond_outline(flat_mcqs)

    # 4. Assemble coverage rollup
    domain_rollup = {
        "Describe cloud concepts":                  len(all_batches["A"]["mcqs"]),
        "Describe Azure architecture and services": len(all_batches["B"]["mcqs"]) + len(all_batches["B-EXT"]["mcqs"]),
        "Describe Azure management and governance": len(all_batches["C"]["mcqs"]) + len(all_batches["C-EXT"]["mcqs"]),
    }
    total = sum(domain_rollup.values())
    domain_pct = {k: round(v * 100 / total, 1) for k, v in domain_rollup.items()}

    # 5. Emit artifact
    artifact = {
        "meta": {
            "schema_version":     "1",
            "source_type":        "llm_knowledge",
            "generator":          "gemini-2.5-pro (Google AI Studio, free tier)",
            "human_reviewed":     True,
            "syllabus_revision":  "2024-09",
            "pipeline_ingest": {
                "segment":   "it",
                "authority": "microsoft",
                "exam":      "az-900",
                "label":     "Microsoft Azure Fundamentals — AZ-900",
            },
            "stats": {
                "mcq_total":         len(flat_mcqs),
                "note_total":        len(flat_notes),
                "domain_counts":     domain_rollup,
                "domain_percent":    domain_pct,
                "difficulty_counts": _count_by(flat_mcqs, "difficulty"),
                "bloom_counts":      _count_by(flat_mcqs, "bloom_level"),
            },
            "known_issues": known_issues,
            "audit_gate": {
                "required":   "vidushak.verify_and_repair()",
                "status":     "pending",
                "note":       "Seed is non-production until Vidushak adversarial pass succeeds.",
            },
        },
        "mcqs":  [{"seq": i + 1, **m} for i, m in enumerate(flat_mcqs)],
        "notes": flat_notes,
    }

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)

    print()
    print(f"Wrote {len(flat_mcqs)} MCQs + {len(flat_notes)} notes -> {OUT_PATH.name}")
    print(f"Domain counts  : {domain_rollup}")
    print(f"Domain percent : {domain_pct}")
    print(f"Difficulty     : {_count_by(flat_mcqs, 'difficulty')}")
    print(f"Bloom          : {_count_by(flat_mcqs, 'bloom_level')}")
    print(f"Known issues   : {len(known_issues)}  {[k['flag'] for k in known_issues]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
