"""
PDF Loader — পাঠ্যপুস্তক থেকে পাঠ্য বের করা
==============================================
Extracts clean text from a PDF file.
Inspired by LlamaIndex's SimpleDirectoryReader chunking pattern.
Uses pdfplumber (no Java dependency unlike pdfminer).
"""

from __future__ import annotations
import re
from pathlib import Path


def load_pdf(path: str, max_chars: int = 80_000) -> str:
    """
    Extract text from a PDF file.
    Strips page headers/footers, collapses whitespace.
    Returns truncated text (max_chars).
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")

    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages: list[str] = []
    with pdfplumber.open(path_obj) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            # Strip page numbers and common header/footer noise
            text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"\s{3,}", "  ", text)
            if text.strip():
                pages.append(text.strip())

    full_text = "\n\n".join(pages)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)

    return full_text[:max_chars]
