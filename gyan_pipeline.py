#!/usr/bin/env python3
"""
Gyan AI — Main Pipeline Orchestrator
======================================
The relay race:  সর্বজ্ঞ → চিত্রগুপ্ত → সূত্রধর → Supabase

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

Stdout is JSON lines (parsed by Next.js /api/pipeline/run):
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

def run(taxonomy: TaxonomySlice) -> PipelineResult:
    start = time.time()
    errors = 0

    emit_progress(f"━━━ Gyan AI Pipeline starting: {taxonomy.label} ━━━")
    emit_progress(f"Step 1/4 — Loading source material")

    # ── Load source ───────────────────────────────────────────────────────────
    try:
        raw_text = load_source_text(taxonomy)
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
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    check_required_env()
    args     = parse_args()
    taxonomy = build_taxonomy(args)

    try:
        result = run(taxonomy)
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
