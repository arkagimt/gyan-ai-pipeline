"""
Supabase Storage Loader — পাঠ্যপুস্তক স্বয়ংক্রিয়ভাবে আনা
=============================================================
Fetches textbook PDFs from Supabase Storage and returns
extracted text — no manual URL needed per pipeline run.

How it works:
  1. Query curriculum_sources table for (board, class_num, subject, chapter)
  2. If found, download PDF bytes from Supabase Storage bucket 'textbook-pdfs'
  3. Extract text via pdfplumber (same as loaders/pdf_loader.py)
  4. Return text to সর্বজ্ঞ as source material

Storage path convention:
  textbook-pdfs/{board_lower}/{class_num}/{subject_slug}.pdf
  e.g.  textbook-pdfs/wbbse/1/bengali.pdf
        textbook-pdfs/cbse/10/science.pdf

If no PDF exists for the node → returns None (pipeline falls back to LLM knowledge).
"""

from __future__ import annotations
import io
import re
import requests
import tempfile
import os

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, emit_progress
from models.schemas import TaxonomySlice


# Bucket holds both PDFs and their OCR'd .txt siblings.
# Convention: if a textbook lives at `wbbse/10/physical-science.pdf`,
# the pre-OCR'd text (produced by scripts/ocr_textbook.py via Marker+Surya)
# lives at `wbbse/10/physical-science.txt`. Pipeline prefers the .txt.
BUCKET      = "textbook-pdfs"
REST_URL    = f"{SUPABASE_URL}/rest/v1"
STORAGE_URL = f"{SUPABASE_URL}/storage/v1"
_HEADERS    = {
    "apikey":        SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type":  "application/json",
}


# ── Storage path helpers ──────────────────────────────────────────────────────

def _subject_slug(subject: str) -> str:
    """'Physical Science' → 'physical-science'"""
    return re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")


def storage_path(board: str, class_num: int, subject: str) -> str:
    return f"{board.lower()}/{class_num}/{_subject_slug(subject)}.pdf"


def txt_sibling_path(pdf_storage_path: str) -> str:
    """`wbbse/10/physical-science.pdf` → `wbbse/10/physical-science.txt`"""
    if pdf_storage_path.endswith(".pdf"):
        return pdf_storage_path[:-4] + ".txt"
    return pdf_storage_path + ".txt"


# ── curriculum_sources lookup ─────────────────────────────────────────────────

def lookup_source(taxonomy: TaxonomySlice) -> dict | None:
    """
    Query curriculum_sources for the best matching PDF source.
    Tries chapter-specific first, then subject-level fallback.
    Returns the row dict or None.
    """
    if not taxonomy.board or not taxonomy.class_num or not taxonomy.subject:
        return None

    try:
        params: dict = {
            "board":     f"eq.{taxonomy.board}",
            "class_num": f"eq.{taxonomy.class_num}",
            "subject":   f"eq.{taxonomy.subject}",
            "is_active": "eq.true",
            "order":     "chapter.desc.nullslast",  # chapter-specific rows first
            "limit":     "1",
        }
        # If chapter specified, try to match it; else get the subject-level PDF
        if taxonomy.chapter:
            params_chapter = {**params, "chapter": f"eq.{taxonomy.chapter}"}
            resp = requests.get(
                f"{REST_URL}/curriculum_sources",
                headers=_HEADERS, params=params_chapter, timeout=10,
            )
            if resp.status_code == 200 and resp.json():
                return resp.json()[0]

        # Subject-level fallback (chapter IS NULL)
        params_subject = {**params, "chapter": "is.null"}
        resp = requests.get(
            f"{REST_URL}/curriculum_sources",
            headers=_HEADERS, params=params_subject, timeout=10,
        )
        if resp.status_code == 200 and resp.json():
            return resp.json()[0]

    except Exception as exc:
        emit_progress(f"[storage] curriculum_sources lookup failed (non-blocking): {exc}")

    return None


# ── PDF download + extract ────────────────────────────────────────────────────

def _download_bytes(storage_path_: str, *, log_404: bool = True) -> bytes | None:
    """Download raw bytes from Supabase Storage. Used for both .pdf and .txt."""
    url = f"{STORAGE_URL}/object/{BUCKET}/{storage_path_}"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.content
        # 404 on the .txt probe is the common path (textbook hasn't been OCR'd yet)
        if resp.status_code != 404 or log_404:
            emit_progress(f"[storage] Download HTTP {resp.status_code} for {storage_path_}")
    except Exception as exc:
        emit_progress(f"[storage] Download error: {exc}")
    return None


# Backward compat — some callers still use the old name.
def _download_pdf_bytes(storage_path_: str) -> bytes | None:
    return _download_bytes(storage_path_)


def _upload_bytes(storage_path_: str, data: bytes, content_type: str) -> bool:
    """Upload bytes to Supabase Storage (PUT — overwrites existing object)."""
    url = f"{STORAGE_URL}/object/{BUCKET}/{storage_path_}"
    headers = {
        "apikey":        SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type":  content_type,
        "x-upsert":      "true",
    }
    try:
        resp = requests.put(url, headers=headers, data=data, timeout=60)
        if resp.status_code in (200, 201):
            return True
        emit_progress(f"[storage] Upload HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        emit_progress(f"[storage] Upload error: {exc}")
    return False


def upload_ocr_text(pdf_storage_path: str, ocr_text: str) -> bool:
    """
    Called by scripts/ocr_textbook.py after running Marker.
    Saves the OCR output as a .txt sibling so future ingest runs skip OCR.
    """
    txt_path = txt_sibling_path(pdf_storage_path)
    return _upload_bytes(
        txt_path,
        ocr_text.encode("utf-8"),
        content_type="text/plain; charset=utf-8",
    )


def _extract_text_from_bytes(pdf_bytes: bytes, max_chars: int = 80_000) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber not installed — run: pip install pdfplumber")

    # Write to temp file (pdfplumber needs file path or file-like object)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        pages: list[str] = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
                text = re.sub(r"\s{3,}", "  ", text)
                if text.strip():
                    pages.append(text.strip())
        full_text = "\n\n".join(pages)
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        return full_text[:max_chars]
    finally:
        os.unlink(tmp_path)


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_textbook_text(taxonomy: TaxonomySlice, max_chars: int = 80_000) -> str | None:
    """
    Main entry point — called by gyan_pipeline.py before running agents.

    Lookup order:
      1. Pre-OCR'd `.txt` sibling (produced by scripts/ocr_textbook.py).
         Bengali boards (WBBSE/WBCHSE) *require* this — pdfplumber can't
         read Bengali Unicode from scanned textbooks reliably.
      2. Raw `.pdf` via pdfplumber (works fine for CBSE/ICSE text PDFs).
      3. None → pipeline falls back to LLM knowledge.
    """
    source_row = lookup_source(taxonomy)
    if not source_row:
        return None

    path = source_row.get("storage_path") or storage_path(
        taxonomy.board, taxonomy.class_num, taxonomy.subject
    )
    label = source_row.get("display_name") or path

    emit_progress(f"[storage] Found textbook: {label}")

    # ── 1. Prefer pre-OCR'd .txt sibling ──────────────────────────────────────
    txt_path  = txt_sibling_path(path)
    txt_bytes = _download_bytes(txt_path, log_404=False)
    if txt_bytes:
        text = txt_bytes.decode("utf-8", errors="replace")
        emit_progress(
            f"[storage] Using pre-OCR'd text ({len(text)} chars) from {txt_path}"
        )
        return text[:max_chars]

    # ── 2. Fallback to raw .pdf ──────────────────────────────────────────────
    # Bengali boards won't get good text from pdfplumber — warn the admin so
    # they know to run scripts/ocr_textbook.py for this source.
    if taxonomy.board in ("WBBSE", "WBCHSE"):
        emit_progress(
            f"[storage] ⚠ No OCR'd .txt found for Bengali textbook «{label}». "
            f"pdfplumber may mangle Bengali script. "
            f"Run scripts/ocr_textbook.py --path {path} to pre-OCR this source."
        )

    pdf_bytes = _download_bytes(path)
    if not pdf_bytes:
        emit_progress(f"[storage] Could not download {path} — falling back to LLM knowledge")
        return None

    emit_progress(f"[storage] Extracting text from {len(pdf_bytes) // 1024} KB PDF...")
    text = _extract_text_from_bytes(pdf_bytes, max_chars=max_chars)
    emit_progress(f"[storage] Extracted {len(text)} chars from textbook")
    return text
