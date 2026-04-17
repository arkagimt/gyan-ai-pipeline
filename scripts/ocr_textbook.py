#!/usr/bin/env python3
"""
OCR a textbook PDF in Supabase Storage → upload .txt sibling
==============================================================
Run once per textbook. Future ingest runs will use the cached .txt and
skip OCR entirely (Marker+Surya is heavy — see loaders/ocr_loader.py).

Usage:
  # OCR a single explicit storage path
  python scripts/ocr_textbook.py --path wbbse/10/physical-science.pdf

  # OCR by taxonomy (looks up curriculum_sources for the PDF path)
  python scripts/ocr_textbook.py --board WBBSE --class 10 \
                                 --subject "Physical Science"

  # Force re-OCR even if a .txt already exists
  python scripts/ocr_textbook.py --path wbbse/10/science.pdf --force

  # Specify languages (default: bn,en — covers all WB cases)
  python scripts/ocr_textbook.py --path cbse/10/science.pdf --langs en,hi

Exit codes:
  0  success — text uploaded
  1  Marker not installed / OCR failed
  2  PDF not found in Supabase Storage
  3  .txt already exists, --force not set
"""

from __future__ import annotations
import argparse
import os
import sys
import tempfile
from pathlib import Path

# Add parent to path so this script can be run standalone from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import emit_progress
from loaders import ocr_loader, supabase_storage_loader as store
from models.schemas import TaxonomySlice, Segment


def _resolve_storage_path(args: argparse.Namespace) -> str | None:
    """Figure out which PDF in storage to OCR."""
    if args.path:
        return args.path.lstrip("/")

    if args.board and args.class_num and args.subject:
        taxonomy = TaxonomySlice(
            segment   = Segment.school,
            board     = args.board,
            class_num = args.class_num,
            subject   = args.subject,
        )
        row = store.lookup_source(taxonomy)
        if row and row.get("storage_path"):
            return row["storage_path"]
        # Fallback to convention-based path
        return store.storage_path(args.board, args.class_num, args.subject)

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR a Supabase Storage textbook PDF via Marker+Surya")
    parser.add_argument("--path",    help="Direct storage path (e.g. wbbse/10/physical-science.pdf)")
    parser.add_argument("--board",   help="Board (WBBSE/WBCHSE/CBSE/ICSE) — used with --class + --subject")
    parser.add_argument("--class",   dest="class_num", type=int)
    parser.add_argument("--subject")
    parser.add_argument("--langs",   default="bn,en", help="Comma-separated Surya lang codes")
    parser.add_argument("--force",   action="store_true", help="Overwrite existing .txt")
    args = parser.parse_args()

    # ── Deps ──────────────────────────────────────────────────────────────────
    if not ocr_loader.is_available():
        print(
            "✗ Marker not installed. This script runs on the OCR worker only.\n"
            "  pip install marker-pdf torch",
            file=sys.stderr,
        )
        return 1

    # ── Resolve path ──────────────────────────────────────────────────────────
    pdf_path = _resolve_storage_path(args)
    if not pdf_path:
        print("✗ Must provide either --path OR (--board --class --subject)", file=sys.stderr)
        return 2

    txt_path = store.txt_sibling_path(pdf_path)
    emit_progress(f"[ocr] Target: {pdf_path}  →  {txt_path}")

    # ── Skip check ────────────────────────────────────────────────────────────
    if not args.force:
        existing = store._download_bytes(txt_path, log_404=False)
        if existing:
            emit_progress(
                f"[ocr] .txt already exists ({len(existing)} bytes). "
                f"Use --force to re-OCR. Skipping."
            )
            return 3

    # ── Download PDF ──────────────────────────────────────────────────────────
    pdf_bytes = store._download_bytes(pdf_path)
    if not pdf_bytes:
        emit_progress(f"[ocr] ✗ PDF not found in storage: {pdf_path}")
        return 2
    emit_progress(f"[ocr] Downloaded {len(pdf_bytes)//1024} KB PDF")

    # ── Run Marker ────────────────────────────────────────────────────────────
    languages = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        emit_progress(f"[ocr] Running Marker (langs={languages})... may take 1–3 min per 50pp")
        text = ocr_loader.ocr_pdf_to_markdown(tmp_path, languages=languages)
    except Exception as e:
        emit_progress(f"[ocr] ✗ Marker failed: {e}")
        return 1
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not text or len(text.strip()) < 100:
        emit_progress(f"[ocr] ✗ OCR produced suspiciously little text ({len(text)} chars) — aborting upload")
        return 1

    emit_progress(f"[ocr] OCR complete: {len(text):,} chars")

    # ── Upload ────────────────────────────────────────────────────────────────
    if store.upload_ocr_text(pdf_path, text):
        emit_progress(f"[ocr] ✓ Uploaded {txt_path} — future ingest runs will skip OCR")
        return 0
    else:
        emit_progress(f"[ocr] ✗ Upload failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
