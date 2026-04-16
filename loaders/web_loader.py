"""
Web Loader — ইন্টারনেট থেকে পাঠ্য বের করা
==========================================
Fetches clean text from a URL.
Strips scripts, styles, navigation — keeps only body content.
"""

from __future__ import annotations
import re
import requests


def load_url(url: str, max_chars: int = 80_000, timeout: int = 20) -> str:
    """
    Fetch a URL and return clean readable text.
    Aggressively strips HTML noise.
    """
    headers = {
        "User-Agent": (
            "GyanAI-Pipeline/1.0 (Educational content indexing bot; "
            "contact: arkagimt@gmail.com)"
        )
    }

    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    html = resp.text

    # Remove script and style blocks entirely
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<nav[\s\S]*?</nav>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<footer[\s\S]*?</footer>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<header[\s\S]*?</header>", " ", html, flags=re.IGNORECASE)

    # Convert block tags to newlines
    html = re.sub(r"<(?:p|div|br|h[1-6]|li|tr)[^>]*>", "\n", html, flags=re.IGNORECASE)

    # Strip all remaining tags
    html = re.sub(r"<[^>]+>", " ", html)

    # Decode common HTML entities
    html = html.replace("&nbsp;", " ").replace("&amp;", "&")
    html = html.replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&quot;", '"').replace("&#39;", "'")

    # Collapse whitespace
    html = re.sub(r"[ \t]{2,}", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)

    return html.strip()[:max_chars]
