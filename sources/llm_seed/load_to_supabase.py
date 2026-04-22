#!/usr/bin/env python3
"""
Seed loader — push audited LLM-knowledge seeds into ingestion_triage_queue
==========================================================================
Usage:
    python -m sources.llm_seed.load_to_supabase az-900

Prerequisites:
  - The seed's ``meta.audit_gate.status`` MUST be ``"passed"``
    (run ``python -m sources.llm_seed.audit <exam>`` first).
  - ``SUPABASE_URL`` + ``SUPABASE_SERVICE_KEY`` must be set.

What it does:
  1. Loads ``sources/llm_seed/<slug>/<slug>-v1.json``.
  2. Hard-asserts audit_gate.status == "passed".
  3. Builds ``StudyPackage`` objects in batches of 25 (MCQs and notes separately).
  4. Calls ``db.supabase_loader.push()`` per batch.
  5. Writes a ``<slug>-v1.load-receipt.json`` trail file with all inserted IDs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# ── Repo-root import guard ────────────────────────────────────────────────────
HERE      = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import check_required_env                                       # noqa: E402
from models.schemas import (                                                # noqa: E402
    TaxonomySlice, MCQItem, MCQOption, StudyNote,
    StudyPackage, SourceType,
    with_derived_scope_nature,
)
from db import supabase_loader                                              # noqa: E402
from sources.llm_seed.audit import EXAM_TAXONOMIES                         # noqa: E402

BATCH_SIZE = 25
SOURCE_URLS: dict[str, str] = {
    "az-900": "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mcq_from_dict(d: dict) -> MCQItem:
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


def _note_from_dict(d: dict) -> StudyNote:
    return StudyNote(
        topic_title     = d["topic_title"],
        summary         = d["summary"],
        key_concepts    = d["key_concepts"],
        formulas        = d.get("formulas", []),
        important_facts = d["important_facts"],
        examples        = d.get("examples", []),
        memory_hooks    = d.get("memory_hooks", []),
    )


def _build_metadata(
    exam_slug: str,
    known_issue_seqs: set[int],
    seq: int | None = None,
) -> dict:
    """Build the metadata dict forwarded into supabase_loader.

    ``exam`` is the sidebar nav-node id (e.g. ``"az-900"``).
    PlatformContext.tsx derives slug from activePath and queries
    ``metadata->>exam`` — so this MUST match the Sidebar.tsx id.
    """
    meta: dict = {
        "exam":             exam_slug,  # web filter key — must match Sidebar id
        "exam_code":        exam_slug,  # alias for admin filtering
        "provenance_tier":  SourceType.llm_knowledge.value,
        "source_type":      SourceType.llm_knowledge.value,
        "source_url":       SOURCE_URLS.get(exam_slug, ""),
        "vidushak_audit":   "passed",
        "confidence":       75,       # conservative baseline for llm_knowledge tier
    }
    if seq is not None and seq in known_issue_seqs:
        meta["scope_flag"] = "beyond_outline"
    return meta


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load audited LLM-knowledge seeds into Supabase ingestion_triage_queue",
    )
    parser.add_argument("exam", help="Exam slug (e.g. az-900)")
    args = parser.parse_args()

    # ── 1. Locate seed + taxonomy ─────────────────────────────────────────────
    exam_dir  = HERE / args.exam
    seed_path = exam_dir / f"{args.exam}-v1.json"
    if not seed_path.is_file():
        print(f"error: no seed artifact at {seed_path}", file=sys.stderr)
        return 2

    base_taxonomy = EXAM_TAXONOMIES.get(args.exam)
    if base_taxonomy is None:
        print(f"error: no taxonomy for {args.exam!r} in EXAM_TAXONOMIES", file=sys.stderr)
        return 2

    # ── 2. Env check ──────────────────────────────────────────────────────────
    check_required_env()

    # ── 3. Load + hard-assert audit gate ──────────────────────────────────────
    art = json.loads(seed_path.read_text(encoding="utf-8"))
    gate_status = art["meta"]["audit_gate"]["status"]
    assert gate_status == "passed", (
        f"REFUSING to load: audit_gate.status is {gate_status!r}, not 'passed'. "
        f"Run `python -m sources.llm_seed.audit {args.exam}` first."
    )

    meta_ingest = art["meta"]["pipeline_ingest"]
    known_issue_seqs = {ki["seq"] for ki in art["meta"].get("known_issues", [])}

    mcqs_raw  = art["mcqs"]
    notes_raw = art.get("notes", [])
    print(f"Loaded {len(mcqs_raw)} MCQs + {len(notes_raw)} notes from {seed_path.name}")
    print(f"  audit_gate: {gate_status}  |  known_issues: {sorted(known_issue_seqs)}")

    # ── 4. Parse all items ────────────────────────────────────────────────────
    mcqs  = [(m["seq"], _mcq_from_dict(m)) for m in mcqs_raw]
    notes = [_note_from_dict(n) for n in notes_raw]

    # ── 5. Push MCQs in batches ───────────────────────────────────────────────
    all_pyq_ids: list[str] = []
    for i in range(0, len(mcqs), BATCH_SIZE):
        batch = mcqs[i : i + BATCH_SIZE]
        batch_mcqs = [item for _, item in batch]
        # Use the first MCQ's topic_tag as batch topic
        first_seq = batch[0][0]
        batch_meta = _build_metadata(args.exam, known_issue_seqs, first_seq)
        # Override per-MCQ scope_flag: build a merged metadata that carries
        # beyond_outline for any MCQ in the batch that's in known_issues.
        # Since push() applies the same metadata to all MCQs in the package,
        # we note: batches of 25 may mix outline/beyond. For simplicity the
        # per-MCQ scope_flag is embedded in each MCQ's metadata individually.
        # We'll do single-MCQ packages for known_issue seqs to isolate the flag.

        # Separate beyond_outline MCQs from normal ones
        normal_mcqs:  list[MCQItem] = []
        outline_mcqs: list[MCQItem] = []
        for seq, mcq in batch:
            if seq in known_issue_seqs:
                outline_mcqs.append(mcq)
            else:
                normal_mcqs.append(mcq)

        if normal_mcqs:
            taxonomy = base_taxonomy.model_copy(update={"topic": normal_mcqs[0].topic_tag})
            taxonomy = with_derived_scope_nature(taxonomy)
            pkg = StudyPackage(
                taxonomy = taxonomy,
                notes    = [],
                mcqs     = normal_mcqs,
                metadata = _build_metadata(args.exam, known_issue_seqs),
            )
            result   = supabase_loader.push(pkg)
            ids      = result.get("pyq_ids", [])
            all_pyq_ids.extend(ids)
            print(f"  MCQ batch {i // BATCH_SIZE + 1}: {len(normal_mcqs)} pushed, {len(ids)} IDs")

        if outline_mcqs:
            for mcq in outline_mcqs:
                taxonomy = base_taxonomy.model_copy(update={"topic": mcq.topic_tag})
                taxonomy = with_derived_scope_nature(taxonomy)
                pkg = StudyPackage(
                    taxonomy = taxonomy,
                    notes    = [],
                    mcqs     = [mcq],
                    metadata = _build_metadata(args.exam, known_issue_seqs, first_seq),
                )
                result   = supabase_loader.push(pkg)
                ids      = result.get("pyq_ids", [])
                all_pyq_ids.extend(ids)
                print(f"  MCQ (beyond_outline): 1 pushed, {len(ids)} IDs")

    # ── 6. Push notes in one batch ────────────────────────────────────────────
    all_material_ids: list[str] = []
    if notes:
        taxonomy = with_derived_scope_nature(base_taxonomy)
        pkg = StudyPackage(
            taxonomy = taxonomy,
            notes    = notes,
            mcqs     = [],
            metadata = _build_metadata(args.exam, known_issue_seqs),
        )
        result = supabase_loader.push(pkg)
        ids    = result.get("material_ids", [])
        all_material_ids.extend(ids)
        print(f"  Notes batch: {len(notes)} pushed, {len(ids)} IDs")

    # ── 7. Write receipt ──────────────────────────────────────────────────────
    receipt = {
        "exam":          args.exam,
        "timestamp_utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "mcq_ids":       all_pyq_ids,
        "material_ids":  all_material_ids,
        "totals": {
            "mcqs_pushed":     len(all_pyq_ids),
            "notes_pushed":    len(all_material_ids),
        },
    }
    receipt_path = exam_dir / f"{args.exam}-v1.load-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n{'='*60}")
    print(f"{len(all_pyq_ids)} MCQs + {len(all_material_ids)} notes pushed to ingestion_triage_queue.")
    print(f"Receipt -> {receipt_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
