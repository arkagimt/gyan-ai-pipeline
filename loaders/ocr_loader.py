"""
OCR Loader — Marker + Surya for Bengali Textbook PDFs
======================================================
Purpose:
  WBBSE / WBCHSE textbooks ship as image-scanned or mixed PDFs with
  Bengali Unicode that pdfplumber cannot reliably extract. Marker
  (https://github.com/VikParuchuri/marker, GPL-3) wraps Surya OCR
  (https://github.com/VikParuchuri/surya, Apache-2 inference, GPL-3 weights)
  and produces publication-quality text preserving tables, equations,
  and reading order.

Architecture decision — OCR is NOT run inside the ingest pipeline:
  • Marker + torch + surya weights weigh ~3GB total
  • Cold start > 5 min, inference 1–3 min per 50-page chapter
  • GitHub Actions ingest workflow has timeout-minutes: 15 — tight

Instead:
  • Run OCR ONCE per textbook via scripts/ocr_textbook.py (or the
    .github/workflows/ocr_textbook.yml manual workflow).
  • Upload the resulting .txt back to Supabase Storage alongside the .pdf.
  • loaders/supabase_storage_loader.py now prefers the .txt variant —
    zero OCR cost on regular ingest runs.

This module is the Marker wrapper. It is soft-imported so the rest of
the pipeline works fine even when Marker isn't installed.

Install (heavy — only on the OCR worker):
  pip install marker-pdf torch
"""

from __future__ import annotations
from pathlib import Path


def is_available() -> bool:
    """Check whether Marker can be imported. Called by scripts/ocr_textbook.py."""
    try:
        import marker  # noqa: F401
        return True
    except ImportError:
        return False


def ocr_pdf_to_markdown(pdf_path: str, languages: list[str] | None = None) -> str:
    """
    Run Marker on a PDF and return the full markdown text.

    Args:
        pdf_path:  Path to the local PDF file.
        languages: Surya language codes, e.g. ["bn", "en"] for Bengali+English.
                   Default ["bn", "en"] — covers all WB textbook cases.

    Returns:
        Markdown string with the full document text.

    Raises:
        RuntimeError if Marker isn't installed.
    """
    if not is_available():
        raise RuntimeError(
            "Marker not installed. On the OCR worker run:\n"
            "  pip install marker-pdf torch"
        )

    if languages is None:
        languages = ["bn", "en"]

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Marker's API changed across versions — try the 1.x converter path first,
    # fall back to the legacy convert_single_pdf() for older releases.
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered

        converter = PdfConverter(
            artifact_dict = create_model_dict(),
            config        = {"languages": languages},
        )
        rendered = converter(str(path))
        text, _, _ = text_from_rendered(rendered)
        return text

    except ImportError:
        # Legacy API (Marker < 1.0)
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models

        models = load_all_models()
        text, _, _ = convert_single_pdf(
            fname     = str(path),
            model_lst = models,
            langs     = languages,
        )
        return text
