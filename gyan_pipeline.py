#!/usr/bin/env python3
"""
Gyan AI — Main Pipeline Orchestrator
======================================
The relay race:  Memory Check → সর্বজ্ঞ → চিত্রগুপ্ত → সূত্রধর → Supabase

Usage (local / GitHub Actions):
  python gyan_pipeline.py --segment school --board WBBSE --class 10 \
                          --subject "Physical Science" --chapter electricity \
                          --count 5

  python gyan_pipeline.py --segment competitive --authority WBPSC \
                          --exam "WBCS Prelims" --topic "History of India" \
                          --count 8

  python gyan_pipeline.py --segment it --provider AWS \
                          --exam "Cloud Practitioner (CLF-C02)" \
                          --topic "Security & Compliance" --count 6

Optional flags:
  --source-url  https://...   # fetch raw content from URL
  --source-pdf  /path/to.pdf  # extract from local PDF
  --force                     # skip dedup memory check, always regenerate

Stdout is JSON lines (parsed by Next.js / Streamlit):
  {"type": "agent",    "agent": "সর্বজ্ঞ", "msg": "..."}
  {"type": "progress", "msg": "..."}
  {"type": "result",   "pyqs": 5, "notes": 1, "errors": 0, "elapsed_s": 14.2}
  {"type": "error",    "msg": "..."}
"""

from __future__ import annotations
import argparse
import json
import sys
import time

from config import check_required_env, emit_progress, emit_error
from models.schemas import TaxonomySlice, Segment, PipelineResult


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gyan AI data ingestion pipeline")
    p.add_argument("--segment",     required=True, choices=["school", "competitive", "it"])
    p.add_argument("--count",       type=int, default=5)
    # School args
    p.add_argument("--board",       default=None)
    p.add_argument("--class",       dest="class_num", type=int, default=None)
    p.add_argument("--subject",     default=None)
    p.add_argument("--chapter",     default=None)
    # Competitive args
    p.add_argument("--authority",   default=None)
    p.add_argument("--exam",        default=None)
    p.add_argument("--topic",       default=None)
    # IT args
    p.add_argument("--provider",    default=None)
    # Source (optional)
    p.add_argument("--source-url",  dest="source_url", default=None)
    p.add_argument("--source-pdf",  dest="source_pdf", default=None)
    p.add_argument("--force",       action="store_true",
                   help="Skip dedup memory check — always regenerate even if content exists")
    return p.parse_args()


# ── Build TaxonomySlice from args ─────────────────────────────────────────────

def build_taxonomy(args: argparse.Namespace) -> TaxonomySlice:
    return TaxonomySlice(
        segment    = Segment(args.segment),
        board      = args.board,
        class_num  = args.class_num,
        subject    = args.subject,
        chapter    = args.chapter,
        authority  = args.authority,
        exam       = args.exam,
        topic      = args.topic,
        provider   = args.provider,
        count      = args.count,
        source_url = args.source_url,
        source_pdf = args.source_pdf,
    )


def apply_dedup_memory(taxonomy: TaxonomySlice, force: bool) -> TaxonomySlice | None:
    """
    Check pipeline memory for existing MCQs on this taxonomy slice.

    Returns:
      None            → skip the pipeline entirely (enough content exists)
      TaxonomySlice   → proceed (original or count-adjusted for top-up mode)

    The --force flag bypasses this check entirely (useful for re-running after
    a bad batch or when you deliberately want more variants).
    """
    if force:
        emit_progress("[memory] --force flag set — skipping dedup check")
        return taxonomy

    from db.memory import check_existing_mcqs
    existing = check_existing_mcqs(taxonomy)

    if existing == 0:
        return taxonomy  # no existing content — full pipeline run

    requested = taxonomy.count

    if existing >= requested:
        emit_progress(
            f"[memory] SKIP — {existing} MCQs already exist for «{taxonomy.label}» "
            f"(requested {requested}). Use --force to regenerate."
        )
        return None  # signal to caller: skip pipeline

    # Top-up: generate only the missing gap
    gap = requested - existing
    emit_progress(
        f"[memory] TOP-UP — generating {gap} more MCQs to reach {requested} "
        f"(already have {existing} for «{taxonomy.label}»)"
    )
    return taxonomy.model_copy(update={"count": gap})


# ── Load source text (if provided) ────────────────────────────────────────────

def load_source_text(taxonomy: TaxonomySlice) -> str:
    if taxonomy.source_url:
        emit_progress(f"Fetching source URL: {taxonomy.source_url}")
        from loaders.web_loader import load_url
        return load_url(taxonomy.source_url)

    if taxonomy.source_pdf:
        emit_progress(f"Loading PDF: {taxonomy.source_pdf}")
        from loaders.pdf_loader import load_pdf
        return load_pdf(taxonomy.source_pdf)

    emit_progress("No source provided — agents will use LLM knowledge")
    return ""


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(taxonomy: TaxonomySlice, force: bool = False) -> PipelineResult:
    start = time.time()
    errors = 0

    emit_progress(f"━━━ Gyan AI Pipeline starting: {taxonomy.label} ━━━")

    # ── Step 0: Dedup Memory Check ────────────────────────────────────────────
    emit_progress("Step 0/4 — Memory check (dedup)")
    taxonomy = apply_dedup_memory(taxonomy, force)
    if taxonomy is None:
        # Enough content already exists — exit cleanly, no tokens spent
        elapsed = round(time.time() - start, 2)
        return PipelineResult(pyqs=0, notes=0, errors=0, elapsed_s=elapsed, skipped=True)

    emit_progress(f"Step 1/4 — Loading source material")

    # ── Load source ───────────────────────────────────────────────────────────
    # Priority: explicit --source-pdf / --source-url > Supabase Storage textbook > LLM knowledge
    try:
        raw_text = load_source_text(taxonomy)

        # If no explicit source given, check Supabase Storage for a stored textbook PDF
        if not raw_text and taxonomy.segment.value == "school" and taxonomy.board and taxonomy.class_num:
            emit_progress("[storage] No explicit source — checking Supabase Storage for textbook PDF")
            from loaders.supabase_storage_loader import fetch_textbook_text
            stored_text = fetch_textbook_text(taxonomy)
            if stored_text:
                raw_text = stored_text
            else:
                emit_progress("[storage] No textbook PDF found — agents will use LLM knowledge")

    except Exception as e:
        emit_error(f"Source loading failed: {e}")
        raw_text = ""
        errors += 1

    # ── সর্বজ্ঞ — Extract ─────────────────────────────────────────────────────
    emit_progress(f"Step 2/4 — সর্বজ্ঞ extracting content")
    from agents import sarbagya
    try:
        extract = sarbagya.run(taxonomy, raw_text)
    except Exception as e:
        emit_error(f"সর্বজ্ঞ failed: {e}")
        return PipelineResult(errors=1, elapsed_s=round(time.time() - start, 2))

    # ── চিত্রগুপ্ত — Validate ─────────────────────────────────────────────────
    emit_progress(f"Step 3/4 — চিত্রগুপ্ত validating")
    from agents import chitragupta
    try:
        report = chitragupta.run(extract)
    except Exception as e:
        emit_error(f"চিত্রগুপ্ত failed: {e}")
        return PipelineResult(errors=1, elapsed_s=round(time.time() - start, 2))

    if not report.is_valid:
        emit_error(f"চিত্রগুপ্ত rejected content: {report.rejection_reason}")
        return PipelineResult(errors=1, elapsed_s=round(time.time() - start, 2))

    # ── সূত্রধর — Generate ────────────────────────────────────────────────────
    emit_progress(f"Step 4/4 — সূত্রধর generating study material")
    from agents import sutradhar
    try:
        package = sutradhar.run(report)
    except Exception as e:
        emit_error(f"সূত্রধর failed: {e}")
        return PipelineResult(errors=1, elapsed_s=round(time.time() - start, 2))

    # ── Push to Supabase ──────────────────────────────────────────────────────
    emit_progress("Pushing to Supabase ingestion_triage_queue")
    from db import supabase_loader
    try:
        pushed = supabase_loader.push(package)
    except Exception as e:
        emit_error(f"Supabase push failed: {e}")
        errors += 1
        pushed = {"pyq_ids": [], "material_ids": []}

    elapsed = round(time.time() - start, 2)
    result = PipelineResult(
        pyqs       = len(pushed["pyq_ids"]),
        notes      = len(pushed["material_ids"]),
        errors     = errors,
        elapsed_s  = elapsed,
        queued_ids = pushed["pyq_ids"] + pushed["material_ids"],
    )

    emit_progress(
        f"━━━ Done in {elapsed}s — "
        f"{result.pyqs} MCQs + {result.notes} notes → triage queue ━━━"
    )

    # ── Post-push: milestone check (Sanjaya) ──────────────────────────────────
    if result.pyqs > 0:
        try:
            from db.memory import after_push_checks
            after_push_checks(result.pyqs)
        except Exception:
            pass  # never let milestone check crash the pipeline

    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    check_required_env()
    args     = parse_args()
    taxonomy = build_taxonomy(args)

    try:
        result = run(taxonomy, force=args.force)
        # Final result line — parsed by Next.js /api/pipeline/run
        print(json.dumps(result.model_dump(), ensure_ascii=False), flush=True)
        sys.exit(0 if result.errors == 0 else 1)

    except KeyboardInterrupt:
        emit_error("Pipeline interrupted")
        sys.exit(130)
    except Exception as e:
        emit_error(f"Pipeline crashed: {e}")
        print(json.dumps({"type": "result", "pyqs": 0, "notes": 0, "errors": 1,
                          "elapsed_s": 0.0, "queued_ids": []}), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
