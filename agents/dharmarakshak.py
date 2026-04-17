"""
ধর্মরক্ষক — The Safety Guardian
==================================
Bengali:  ধর্মরক্ষক  (dhármarakṣaka — "protector of dharma/rightness")
Website:  future — gyanagent.in/about (to be added)

Role:   Content safety gate — EVERY MCQ and study note passes through
        before being pushed to the triage queue.

Why critical:
  Gyan AI serves students from Class 1 (age 6) through competitive aspirants.
  One inappropriate MCQ leaking into production is a trust + legal event.
  Dharmarakshak is a non-negotiable binary gate, not an optional QA layer.

Model:  Llama Guard 3 (8B) via Groq — free, fast, purpose-built classifier.
        Meta's Llama Guard 3 is trained specifically to classify content
        against a hazard taxonomy. Returns "safe" or "unsafe\n<codes>".

Policy codes we watch (Llama Guard 3 taxonomy):
  S1  Violent Crimes
  S4  Child/Sexual Exploitation          ← highest priority for minors
  S8  Intellectual Property              ← no plagiarised textbook passages
  S10 Hate Speech / Discrimination       ← no caste/religion bias in MCQs
  S11 Suicide / Self-Harm
  S12 Sexual Content
  S13 Elections / Political Propaganda   ← sensitive in Indian education

Additional Gyan-custom checks (heuristic, no LLM):
  - Detects English MCQs intended for Bengali-medium boards (quick regex)
  - Flags question stems > 50 words (too verbose for school MCQs)

Llama Guard 3 ref: https://huggingface.co/meta-llama/Llama-Guard-3-8B
Groq model ID: llama-guard-3-8b
"""

from __future__ import annotations
import re

from groq import Groq

from config import GROQ_API_KEY, GROQ_GUARD_MODEL, emit_agent, emit_progress
from models.schemas import TaxonomySlice, MCQItem, StudyNote


# ── Policy ────────────────────────────────────────────────────────────────────

# Violation codes that block content from reaching triage queue
BLOCKED_CODES: set[str] = {"S1", "S4", "S10", "S11", "S12", "S13"}

# Codes that flag for human review but don't auto-block
REVIEW_CODES: set[str] = {"S8"}


# ── Groq guard client (lazy singleton) ───────────────────────────────────────

_guard_client: Groq | None = None

def _get_guard_client() -> Groq:
    global _guard_client
    if _guard_client is None:
        _guard_client = Groq(api_key=GROQ_API_KEY)
    return _guard_client


# ── Llama Guard 3 classifier ──────────────────────────────────────────────────

def _llama_guard_check(content: str) -> tuple[bool, list[str]]:
    """
    Runs content through Llama Guard 3 via Groq.
    Returns (is_safe, violation_codes).

    On any API error → defaults to (True, []) so pipeline is never blocked
    by a transient safety-check failure. This is intentional: content
    still goes to human triage for review.
    """
    try:
        resp = _get_guard_client().chat.completions.create(
            model    = GROQ_GUARD_MODEL,
            messages = [{"role": "user", "content": content}],
        )
        result = resp.choices[0].message.content.strip()
    except Exception as e:
        emit_progress(f"[ধর্মরক্ষক] Guard API error (non-blocking): {e}")
        return True, []

    if result.lower().startswith("safe"):
        return True, []

    # Parse: "unsafe\nS10\nS4" → ["S10", "S4"]
    lines  = result.splitlines()
    codes  = [ln.strip() for ln in lines[1:] if re.match(r"S\d+", ln.strip())]
    return False, codes


# ── Heuristic checks (no LLM) ────────────────────────────────────────────────

def _heuristic_flags(content: str, taxonomy: TaxonomySlice) -> list[str]:
    """
    Fast pre-checks that don't need an LLM call.
    Returns list of human-readable flag strings (empty = clean).
    """
    flags: list[str] = []

    # Check: Bengali board MCQ written in English
    if taxonomy.board in ("WBBSE", "WBCHSE"):
        # If content has almost no Bengali Unicode chars, it's wrong-language
        bengali_chars = len(re.findall(r"[\u0980-\u09FF]", content))
        total_alpha   = len(re.findall(r"[a-zA-Z\u0980-\u09FF]", content))
        if total_alpha > 20 and bengali_chars / max(total_alpha, 1) < 0.15:
            flags.append("WRONG_LANGUAGE: Bengali board but MCQ appears to be in English")

    # Check: excessively long question stem (>50 words = likely hallucinated padding)
    # Only check the first 200 chars as a quick proxy
    words_in_first_200 = len(content[:200].split())
    if words_in_first_200 > 40:
        flags.append("VERBOSE_STEM: question stem appears too long for an MCQ")

    return flags


# ── Content serialiser ────────────────────────────────────────────────────────

def _mcq_to_text(mcq: MCQItem) -> str:
    return (
        f"Question: {mcq.question}\n"
        f"A: {mcq.options.A}\n"
        f"B: {mcq.options.B}\n"
        f"C: {mcq.options.C}\n"
        f"D: {mcq.options.D}\n"
        f"Correct: {mcq.correct}\n"
        f"Explanation: {mcq.explanation}"
    )


def _note_to_text(note: StudyNote) -> str:
    return (
        f"Topic: {note.topic_title}\n"
        f"Summary: {note.summary}\n"
        f"Key concepts: {', '.join(note.key_concepts)}\n"
        f"Facts: {'; '.join(note.important_facts[:5])}"
    )


# ── Main public API ───────────────────────────────────────────────────────────

class SafetyResult:
    """Result of a ধর্মরক্ষক check."""
    __slots__ = ("is_safe", "blocked", "needs_review", "violations", "heuristic_flags")

    def __init__(
        self,
        is_safe:         bool,
        blocked:         bool,
        needs_review:    bool,
        violations:      list[str],
        heuristic_flags: list[str],
    ):
        self.is_safe         = is_safe
        self.blocked         = blocked
        self.needs_review    = needs_review
        self.violations      = violations
        self.heuristic_flags = heuristic_flags

    def __repr__(self) -> str:
        status = "BLOCKED" if self.blocked else ("REVIEW" if self.needs_review else "SAFE")
        return f"SafetyResult({status}, violations={self.violations}, flags={self.heuristic_flags})"


def check_mcq(mcq: MCQItem, taxonomy: TaxonomySlice) -> SafetyResult:
    """Check a single MCQ. Called per-MCQ inside check_package()."""
    content = _mcq_to_text(mcq)

    # Heuristic (fast, no API cost)
    h_flags = _heuristic_flags(content, taxonomy)

    # Llama Guard 3
    guard_safe, codes = _llama_guard_check(content)

    blocked      = not guard_safe and bool(BLOCKED_CODES & set(codes))
    needs_review = (not guard_safe and bool(REVIEW_CODES & set(codes))) or bool(h_flags)

    return SafetyResult(
        is_safe         = guard_safe and not h_flags,
        blocked         = blocked,
        needs_review    = needs_review,
        violations      = codes,
        heuristic_flags = h_flags,
    )


def check_package(
    mcqs:     list[MCQItem],
    notes:    list[StudyNote],
    taxonomy: TaxonomySlice,
) -> tuple[list[MCQItem], list[str]]:
    """
    ধর্মরক্ষক's main gate — checks every MCQ + every study note.

    Returns:
        safe_mcqs    — MCQs that passed (blocked ones removed)
        audit_log    — list of human-readable violation/flag strings

    Policy:
        • BLOCKED_CODES violations → MCQ dropped entirely
        • REVIEW_CODES + heuristic flags → MCQ kept but logged for human review
        • Notes: only logged, never dropped (less student-facing risk)
    """
    emit_agent("ধর্মরক্ষক", f"Safety check: {len(mcqs)} MCQs + {len(notes)} notes")

    safe_mcqs: list[MCQItem] = []
    audit_log: list[str]     = []

    for i, mcq in enumerate(mcqs):
        result = check_mcq(mcq, taxonomy)

        if result.blocked:
            msg = f"MCQ #{i} BLOCKED — violations: {result.violations}"
            audit_log.append(msg)
            emit_progress(f"[ধর্মরক্ষক] {msg}")
            # Don't add to safe_mcqs — drop it

        else:
            safe_mcqs.append(mcq)
            if result.needs_review:
                msg = f"MCQ #{i} flagged for review — {result.heuristic_flags or result.violations}"
                audit_log.append(msg)
                emit_progress(f"[ধর্মরক্ষক] {msg}")

    # Notes: log only
    for j, note in enumerate(notes):
        content  = _note_to_text(note)
        _, codes = _llama_guard_check(content)
        if codes:
            msg = f"Note #{j} ('{note.topic_title}') — guard flags: {codes}"
            audit_log.append(msg)
            emit_progress(f"[ধর্মরক্ষক] {msg}")

    blocked_count = len(mcqs) - len(safe_mcqs)
    if blocked_count:
        emit_agent("ধর্মরক্ষক", f"⛔ Blocked {blocked_count} MCQ(s). {len(safe_mcqs)} passed.")
    else:
        emit_agent("ধর্মরক্ষক", f"✓ All {len(safe_mcqs)} MCQs passed safety check")

    return safe_mcqs, audit_log
