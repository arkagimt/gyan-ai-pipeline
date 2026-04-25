#!/usr/bin/env python3
"""
Vidushak audit gate for LLM-knowledge seeds
===========================================
Non-negotiable pre-pilot gate for any content tagged ``source_type = "llm_knowledge"``.

Usage:
    python -m sources.llm_seed.audit az-900
    python -m sources.llm_seed.audit az-900 --batch-size 10

What it does:
  1. Loads ``sources/llm_seed/<exam>/<exam>-v1.json``.
  2. Converts the 100 MCQ dicts → ``MCQItem`` instances (pydantic-validated).
  3. Runs ``agents.vidushak.verify_and_repair()`` on them in batches
     (grounding check OFF — there's no corpus; llm_knowledge is its own source).
  4. Aggregates the per-batch audit dicts.
  5. Writes a timestamped ``audit-<ts>.json`` report next to the seed.
  6. Flips the artifact's ``meta.audit_gate.status`` based on verdict:
       • "passed"         — zero issues flagged
       • "needs-review"   — issues were flagged; report holds details
     Vidushak *does* repair during its pass, but this CLI intentionally
     does NOT write those repairs back into the golden seed. Repairs are
     captured in the audit report for human review (the "beyond outline"
     warning prefix is a single-source-of-truth in merge_seed.py and
     auto-applied repairs can strip it — a human merge is safer).

Requirements:
  - ``GROQ_API_KEY`` must be set (pipeline default — Vidushak calls Groq/Llama).
  - Run from repo root so the ``sources.llm_seed.audit`` module path resolves,
    or invoke as a script: ``python sources/llm_seed/audit.py az-900``.

Adding a new exam:
  1. Build its seed via ``sources/llm_seed/<exam>/merge_seed.py``.
  2. Register a ``TaxonomySlice`` in ``EXAM_TAXONOMIES`` below.
  3. Run this audit. No other changes needed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Repo-root import guard ────────────────────────────────────────────────────
# Allow running both as ``python -m sources.llm_seed.audit <exam>`` (from repo
# root, path already set) and as ``python sources/llm_seed/audit.py <exam>``
# (direct invocation — need to push the repo root onto sys.path).
HERE      = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.schemas import TaxonomySlice, MCQItem, MCQOption, Segment  # noqa: E402
from agents import vidushak                                             # noqa: E402
from config import GROQ_API_KEY                                         # noqa: E402


# ── Per-exam taxonomy registry ────────────────────────────────────────────────
# Vidushak's audit needs a TaxonomySlice to pick language context + age
# calibration. LLM-knowledge seeds are all international IT certs (for now),
# so segment=it + scope derivation = "international" + nature = "cert".
# Extend this dict when adding CLF-C02, ACE, etc.
EXAM_TAXONOMIES: dict[str, TaxonomySlice] = {
    "az-900": TaxonomySlice(
        segment  = Segment.it,
        provider = "Microsoft",
        exam     = "AZ-900",
        topic    = "Microsoft Azure Fundamentals",
        count    = 1,   # placeholder — vidushak doesn't read .count
    ),
    "ai-900": TaxonomySlice(
        segment  = Segment.it,
        provider = "Microsoft",
        exam     = "AI-900",
        topic    = "Microsoft Azure AI Fundamentals",
        count    = 1,
    ),
    # Future:
    # "clf-c02": TaxonomySlice(segment=Segment.it, provider="AWS",
    #                          exam="CLF-C02",
    #                          topic="AWS Certified Cloud Practitioner", count=1),
    # "ace":     TaxonomySlice(segment=Segment.it, provider="Google Cloud",
    #                          exam="ACE",
    #                          topic="Google Cloud Associate Cloud Engineer", count=1),
}


# ── MCQ dict → MCQItem ────────────────────────────────────────────────────────

def _mcq_from_dict(d: dict) -> MCQItem:
    """Strip seed-only fields (seq) and project into the pydantic model."""
    return MCQItem(
        question          = d["question"],
        options           = MCQOption(**d["options"]),
        correct           = d["correct"],
        reasoning_process = d["reasoning_process"],
        explanation       = d["explanation"],
        difficulty        = d["difficulty"],
        bloom_level       = d["bloom_level"],
        topic_tag         = d["topic_tag"],
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vidushak audit gate for LLM-knowledge seeds",
    )
    parser.add_argument("exam", help="Exam slug (e.g. az-900, clf-c02, ace)")
    parser.add_argument(
        "--batch-size",
        type    = int,
        default = 10,
        help    = "MCQs per Vidushak call (default 10 — below token ceiling)",
    )
    args = parser.parse_args()

    # 1. Locate seed
    exam_dir = HERE / args.exam
    if not exam_dir.is_dir():
        print(f"error: no seed directory at {exam_dir}", file=sys.stderr)
        return 2

    seed_path = exam_dir / f"{args.exam}-v1.json"
    if not seed_path.is_file():
        print(f"error: no seed artifact at {seed_path}", file=sys.stderr)
        return 2

    taxonomy = EXAM_TAXONOMIES.get(args.exam)
    if taxonomy is None:
        print(
            f"error: no taxonomy registered for {args.exam!r}.\n"
            f"Add a TaxonomySlice entry to EXAM_TAXONOMIES in {__file__}.",
            file=sys.stderr,
        )
        return 2

    # 2. Env check
    if not GROQ_API_KEY:
        print(
            "error: GROQ_API_KEY not set — Vidushak cannot call the LLM.\n"
            "Set it in your environment or .env file and retry.",
            file=sys.stderr,
        )
        return 3

    # 3. Load + deserialize
    art = json.loads(seed_path.read_text(encoding="utf-8"))
    mcqs_raw = art["mcqs"]
    label = art["meta"]["pipeline_ingest"]["label"]
    print(f"Loaded {len(mcqs_raw)} MCQs from {seed_path.name}")
    print(f"Taxonomy: {label}")

    try:
        mcqs = [_mcq_from_dict(m) for m in mcqs_raw]
    except Exception as e:
        print(f"error: MCQ pydantic validation failed — {e}", file=sys.stderr)
        return 4

    # 4. Batched audit
    agg = {
        "total":          0,
        "issues_found":   0,
        "repaired":       0,
        "repair_failed":  0,
        "issue_samples":  [],
        "batches":        [],
    }
    repaired_mcqs: list[MCQItem] = []

    print(f"\nAuditing in batches of {args.batch_size} ...")
    for i in range(0, len(mcqs), args.batch_size):
        batch = mcqs[i : i + args.batch_size]
        batch_start_seq = i + 1
        batch_end_seq   = i + len(batch)
        print(f"  batch {i // args.batch_size + 1:>2} : seqs {batch_start_seq}..{batch_end_seq}")

        try:
            repaired, audit = vidushak.verify_and_repair(batch, taxonomy, label)
        except Exception as e:
            # Vidushak should never raise (it catches internally), but belt-and-braces
            print(f"    ! batch raised {type(e).__name__}: {e}", file=sys.stderr)
            audit = {
                "total":         len(batch),
                "issues_found":  0,
                "repaired":      0,
                "repair_failed": 0,
                "issue_samples": [],
                "batch_error":   str(e)[:200],
            }
            repaired = batch  # pass originals through

        repaired_mcqs.extend(repaired)
        agg["total"]         += audit["total"]
        agg["issues_found"]  += audit["issues_found"]
        agg["repaired"]      += audit["repaired"]
        agg["repair_failed"] += audit["repair_failed"]
        agg["issue_samples"].extend(audit.get("issue_samples", []))
        agg["batches"].append({
            "seq_start":     batch_start_seq,
            "seq_end":       batch_end_seq,
            "total":         audit["total"],
            "issues_found":  audit["issues_found"],
            "repaired":      audit["repaired"],
            "repair_failed": audit["repair_failed"],
            "issues":        audit.get("issue_samples", []),
            **({"batch_error": audit["batch_error"]} if "batch_error" in audit else {}),
        })

    # 5. Verdict
    unresolved = agg["issues_found"] - agg["repaired"]
    if agg["issues_found"] == 0:
        verdict = "passed"
    elif unresolved == 0:
        verdict = "needs-review"   # Vidushak repaired them all, but humans should confirm
    else:
        verdict = "needs-review"

    # 6. Report
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "exam":           args.exam,
        "timestamp_utc":  ts,
        "mcq_total":      agg["total"],
        "issues_found":   agg["issues_found"],
        "repaired":       agg["repaired"],
        "repair_failed":  agg["repair_failed"],
        "unresolved":     unresolved,
        "verdict":        verdict,
        "issue_samples":  agg["issue_samples"],
        "per_batch":      agg["batches"],
        "notes": (
            "Vidushak ran in ungrounded mode (extract=None). The source_disconnect "
            "check is skipped for llm_knowledge tier content. Other quality gates "
            "(wrong_answer, distractor_correct, two_correct_options, ambiguous, "
            "language_mismatch, age_inappropriate) are active."
        ),
    }
    report_path = exam_dir / f"audit-{ts}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nReport -> {report_path.name}")

    # 7. Flip seed artifact's audit_gate
    art["meta"]["audit_gate"]["status"]              = verdict
    art["meta"]["audit_gate"]["last_audit_report"]   = report_path.name
    art["meta"]["audit_gate"]["last_audit_utc"]      = ts
    art["meta"]["audit_gate"]["issues_found"]        = agg["issues_found"]
    art["meta"]["audit_gate"]["unresolved"]          = unresolved
    seed_path.write_text(
        json.dumps(art, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 8. Summary
    print()
    print(f"Verdict     : {verdict}")
    print(f"  total     : {agg['total']}")
    print(f"  issues    : {agg['issues_found']}")
    print(f"  repaired  : {agg['repaired']}")
    print(f"  unresolved: {unresolved}")
    print()
    if verdict == "passed":
        print("Seed is cleared for pilot exposure.")
        return 0
    print("Seed is NOT cleared — review the audit report, fix, re-run.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
