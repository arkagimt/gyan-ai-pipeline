"""
ভাষাচার্য — The Language Purist
==================================
Bengali:  ভাষাচার্য
Website:  gyanagent.in/about  →  (Phase 17 — planned)

Role:   Second-opinion Bengali grammar/spelling auditor. Runs AFTER বিদূষক
        (so the verifier has already done content correctness checks) and
        flags language-level issues বিদূষক isn't specifically tuned for:

          - matra confusion (ি vs ী, ু vs ূ, ে vs ৈ)
          - y/ja confusion (য় vs য vs ্য)
          - anusvar / chandrabindu / visarga (ং vs ঁ vs ঃ)
          - conjunct (যুক্তাক্ষর) spelling
          - common loanword transliteration drift
          - sentence-final punctuation (।)
          - age-register mismatch (ornate tatsama words in Class 1–4 content)

Non-blocking. Emits `bhashacharya_audit` into StudyPackage.metadata for
admin triage review, but does NOT drop MCQs. Language quality is
subjective enough that a human should decide — ভাষাচার্য surfaces, the
admin decides.

Why separate from বিদূষক:
  বিদূষক's SOURCE_DISCONNECT / wrong-answer checks are factual; they
  should block promotion if grounded. Bengali spelling is stylistic and
  opinion-sensitive. Mixing them in one prompt dilutes both checks.

Cost discipline:
  - Only runs if taxonomy.board ∈ {WBBSE, WBCHSE} (Bengali-medium boards).
  - Skipped silently otherwise. Zero cost for English content.
  - Batches all MCQs in ONE LLM call — cheaper than per-MCQ audit.

When to build this out further:
  - Phase 17+: add a per-MCQ corpus check against Sarbagya's OCR'd
    textbook text (catches spelling drift from the source material).
  - Phase 17++: add pgvector similarity against a curated Bengali
    lexicon (Saṁsad / Bangla Academy dictionaries) once Anveshak lands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from config import get_agent_prompt, emit_agent, emit_progress
from llm import call_llm
from models.schemas import MCQItem, TaxonomySlice


# ── Output schema ─────────────────────────────────────────────────────────────

class LanguageIssue(BaseModel):
    """One flagged issue in one MCQ. LLM fills these; we render for admin."""
    mcq_index:   int    = Field(description="0-based index into the MCQ batch")
    category:    Literal[
        "matra",
        "ya_ja",
        "anusvar",
        "conjunct",
        "loanword",
        "punctuation",
        "register_mismatch",
        "other",
    ]
    severity:    Literal["low", "medium", "high"] = "medium"
    original:    str    = Field(description="The problematic word/phrase as-written")
    suggested:   str    = Field(description="Proposed correction")
    explanation: str    = Field(description="1 short sentence in English — why")


class LanguageAudit(BaseModel):
    """ভাষাচার্য's batch output for one StudyPackage."""
    issues: list[LanguageIssue] = Field(default_factory=list)
    summary: str = Field(
        default="",
        description="1-sentence overall assessment of batch language quality",
    )


# ── Trigger gate ──────────────────────────────────────────────────────────────

_BENGALI_BOARDS = ("WBBSE", "WBCHSE")

# Rough heuristic: has at least N Bengali Unicode characters.
_BN_RANGE = re.compile(r"[\u0980-\u09FF]")

def _is_bengali_content(mcqs: list[MCQItem], threshold: int = 20) -> bool:
    total = 0
    for m in mcqs:
        total += len(_BN_RANGE.findall(m.question or ""))
        if total >= threshold:
            return True
    return False


def should_run(taxonomy: TaxonomySlice, mcqs: list[MCQItem]) -> bool:
    """
    True when ভাষাচার্য should be invoked. Cheap guard — called before the
    pipeline spends any LLM tokens.
    """
    if (taxonomy.board or "") in _BENGALI_BOARDS:
        return True
    # Defensive: some rows may have Bengali content without a Bengali board
    # (cross-board prep material, migrated legacy rows). Audit them anyway.
    return _is_bengali_content(mcqs)


# ── System prompt (fallback — normally loaded from Supabase agent_prompts) ────

_DEFAULT_SYSTEM = """
তুমি ভাষাচার্য — a Bengali language purist reviewing MCQ text for spelling and grammar.

Your ONLY job is to flag Bengali language-level issues. Do NOT comment on factual
correctness (that's বিদূষক's job). Do NOT rewrite the question — just flag.

Focus areas, in priority order:
1. MATRA errors — ি/ী, ু/ূ, ে/ৈ confusion (most common error)
2. য়/য/্য confusion (e.g. নৃত্য vs নৃত‍্য vs নৃতয়)
3. ং vs ঁ vs ঃ misuse
4. Incorrect conjuncts (যুক্তাক্ষর): ক্ষ, জ্ঞ, হ্ন, হ্ম, etc.
5. Loanword spelling (English/Sanskrit origin words that drift — ইংরেজি vs ইংরাজি)
6. Sentence-final punctuation (। not . for Bengali sentences)
7. Register mismatch for the target class level

RULES:
- If the MCQ is entirely in English (e.g. IT content), return empty issues list.
- If Bengali is correct, return empty issues list with a positive summary.
- NEVER invent issues to look thorough. Empty list is a valid answer.
- severity=high only for errors that would confuse a native reader.
- severity=low for stylistic preferences.
- Keep `explanation` under 15 English words.
""".strip()


# ── Main API ──────────────────────────────────────────────────────────────────

def audit(mcqs: list[MCQItem], taxonomy: TaxonomySlice) -> LanguageAudit:
    """
    Run ভাষাচার্য over a batch of MCQs. Returns a LanguageAudit.
    Always returns — never raises — language check must never block a pipeline.

    Caller should attach the returned audit to StudyPackage.metadata["bhashacharya_audit"].
    """
    if not should_run(taxonomy, mcqs):
        return LanguageAudit(summary="skipped — not Bengali content")

    emit_agent("ভাষাচার্য", f"Auditing {len(mcqs)} MCQs for Bengali language quality")

    # Build the batch prompt — one LLM call for all MCQs in the package.
    lines = [
        f"CLASS: {taxonomy.class_num or 'unknown'} · BOARD: {taxonomy.board or 'unknown'}",
        f"SUBJECT: {taxonomy.subject or 'unknown'}",
        "",
        "MCQs to audit (index → question + options):",
    ]
    for i, m in enumerate(mcqs):
        lines.append(f"\n[{i}] {m.question}")
        lines.append(f"    A. {m.options.A}")
        lines.append(f"    B. {m.options.B}")
        lines.append(f"    C. {m.options.C}")
        lines.append(f"    D. {m.options.D}")
        lines.append(f"    explanation: {m.explanation}")

    user_prompt = "\n".join(lines)

    # Try to load custom system prompt from Supabase; fall back to _DEFAULT_SYSTEM.
    try:
        prompt_cfg = get_agent_prompt("bhashacharya")
        system_prompt = prompt_cfg.system_prompt or _DEFAULT_SYSTEM
        temperature   = prompt_cfg.temperature
    except Exception:
        system_prompt = _DEFAULT_SYSTEM
        temperature   = 0.1

    try:
        result: LanguageAudit = call_llm(
            system         = system_prompt,
            user           = user_prompt,
            response_model = LanguageAudit,
            temperature    = temperature,
            max_tokens     = 2048,
            max_retries    = 2,
            language       = "bn",   # route to Sarvam — it understands Bengali errors best
        )
    except Exception as e:
        emit_progress(f"[ভাষাচার্য] audit failed: {type(e).__name__}: {e}"[:200])
        return LanguageAudit(summary=f"audit_error: {type(e).__name__}")

    # Clamp indices — defensive: LLM sometimes returns out-of-range indices
    result.issues = [
        iss for iss in result.issues
        if 0 <= iss.mcq_index < len(mcqs)
    ]

    emit_agent(
        "ভাষাচার্য",
        f"Audit complete — {len(result.issues)} issue(s) flagged across {len(mcqs)} MCQs",
    )
    return result


def audit_to_dict(a: LanguageAudit) -> dict:
    """Serialisation for StudyPackage.metadata['bhashacharya_audit']."""
    return {
        "summary":      a.summary,
        "issue_count":  len(a.issues),
        "issues":       [i.model_dump() for i in a.issues],
    }


__all__ = [
    "audit", "audit_to_dict", "should_run",
    "LanguageAudit", "LanguageIssue",
]
