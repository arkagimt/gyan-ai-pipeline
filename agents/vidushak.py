"""
বিদূষক — The Adversarial Critic
=================================
Bengali:  বিদূষক
Website:  gyanagent.in/about  →  "সূত্রধর যা তৈরি করেছে, আমি তা পরীক্ষা করব।
           হ্যালুসিনেশন বা ভুল তথ্য? বাতিল।"
           (Whatever Sutradhar creates, I'll test it.
            Hallucination or wrong info? Rejected.)

Role:   MCQ adversarial critic — self-critique + repair pass
Input:  list[MCQItem] + TaxonomySlice (for language/age context) + topic label
Output: list[MCQItem] (same length — repaired where needed)

Extracted from agents/sutradhar.py where it lived as _verify_mcqs().
Now a first-class agent so the website persona matches the code.

Upgraded additions (v2):
  5. LANGUAGE_MISMATCH  — MCQ written in wrong language for the board
     (e.g. English questions for WBBSE Bengali-medium students)
  6. AGE_INAPPROPRIATE  — question exceeds cognitive level for stated class
     (e.g. statistics/meta-questions for Class 1-2, bloom=analyze for Class 3)

Pattern:  Guardrails AI "reask" (Apache 2.0) — LLM audits its own output
          and repairs genuine errors before they reach students.
"""

from __future__ import annotations

from config import (
    MAX_RETRIES, get_agent_prompt, emit_agent, emit_progress,
)
from llm import call_llm
from models.schemas import TaxonomySlice, MCQItem, MCQBatchVerification


# ── Verifier system prompt ────────────────────────────────────────────────────

_VERIFIER_SYSTEM = """
You are a strict MCQ quality auditor for an Indian education platform serving
students from Class 1 through competitive exam aspirants.
Your job: find GENUINE errors — not stylistic preferences.

Check each MCQ for these SPECIFIC issues only:

  1. DISTRACTOR_CORRECT  — a 'wrong' option that is actually also correct
     (most common in physics/math: e.g. P=IV listed as distractor when valid)

  2. WRONG_ANSWER        — the marked correct option is factually incorrect

  3. TWO_CORRECT_OPTIONS — more than one option is unambiguously correct

  4. AMBIGUOUS_QUESTION  — question can be reasonably interpreted multiple ways

  5. LANGUAGE_MISMATCH   — MCQ is written in the WRONG LANGUAGE for the board:
     • WBBSE / WBCHSE = Bengali-medium boards → questions and options MUST be
       in Bengali (বাংলা Unicode). If they are in English, flag this.
     • CBSE / ICSE / competitive / IT → English is correct.

  6. AGE_INAPPROPRIATE   — question is beyond (or below) the cognitive level:
     • Class 1-2: ONLY simple concrete facts from the lesson. FORBIDDEN: any
       abstract concept, statistic, meta-question about the subject itself.
     • Class 3-4: FORBIDDEN: analysis, statistics, abstract theory.
     • Class 5-8: Should be age-appropriate — flag only obvious overreach.
     • Class 9-12 & competitive: No restrictions, flag only genuine errors.

Do NOT flag:
  - Minor wording preferences
  - Difficulty level opinions
  - Bloom level disagreements (unless clearly violating class restrictions)

Be conservative: only flag issues you are CERTAIN about.
verdict must be exactly "ok" or "has_issue".
"""


# ── Context helpers ───────────────────────────────────────────────────────────

def _board_language_context(taxonomy: TaxonomySlice) -> str:
    """Returns a one-liner that tells the verifier what language to expect."""
    if taxonomy.board in ("WBBSE", "WBCHSE"):
        return f"EXPECTED LANGUAGE: Bengali (বাংলা) — board is {taxonomy.board}"
    return f"EXPECTED LANGUAGE: English — board is {taxonomy.board or 'N/A'}"


def _class_context(taxonomy: TaxonomySlice) -> str:
    if taxonomy.class_num:
        return f"CLASS: {taxonomy.class_num} (age calibration enforced)"
    return "CLASS: N/A"


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_verification_prompt(
    mcqs: list[MCQItem],
    taxonomy: TaxonomySlice,
    label: str,
) -> str:
    mcq_text = "\n\n".join(
        f"MCQ #{i}:\n"
        f"  Q: {m.question}\n"
        f"  A: {m.options.A}\n"
        f"  B: {m.options.B}\n"
        f"  C: {m.options.C}\n"
        f"  D: {m.options.D}\n"
        f"  Correct: {m.correct}\n"
        f"  Difficulty: {m.difficulty}  |  Bloom: {m.bloom_level}"
        for i, m in enumerate(mcqs)
    )
    return f"""
Topic: {label}
{_board_language_context(taxonomy)}
{_class_context(taxonomy)}
Segment: {taxonomy.segment.value}

Review these {len(mcqs)} MCQs for factual, logical, language, or age-level errors:

{mcq_text}

For each MCQ return:
  index:   the MCQ number (0-based)
  verdict: "ok" or "has_issue"
  issue:   null if ok, specific description if has_issue
           Examples:
             "Option C (P = IV) is also a valid power formula — two correct answers"
             "Question is in English but board is WBBSE (Bengali-medium)"
             "Asks about number of non-native speakers — meta-question, Class 1 student"

Set any_issues=true if ANY MCQ has verdict="has_issue".
""".strip()


def _build_fix_prompt(
    mcq: MCQItem,
    issue: str,
    taxonomy: TaxonomySlice,
    label: str,
) -> str:
    lang_note = (
        "IMPORTANT: This is a WBBSE/WBCHSE Bengali-medium board. "
        "Rewrite the question, options, and explanation IN BENGALI (বাংলা Unicode)."
        if taxonomy.board in ("WBBSE", "WBCHSE")
        else ""
    )
    age_note = ""
    if taxonomy.class_num and taxonomy.class_num <= 2:
        age_note = (
            "IMPORTANT: Class 1-2 student (age 6-7). "
            "Keep question SHORT (max 10 words), options 1-3 words. "
            "Only simple concrete facts. No meta-questions about the subject."
        )
    elif taxonomy.class_num and taxonomy.class_num <= 4:
        age_note = "IMPORTANT: Class 3-4 student. No abstract concepts or statistics."

    return f"""
Topic: {label}
Board: {taxonomy.board or 'N/A'}  |  Class: {taxonomy.class_num or 'N/A'}
{lang_note}
{age_note}

This MCQ has a quality issue that MUST be fixed: {issue}

Original MCQ:
  Question: {mcq.question}
  A: {mcq.options.A}
  B: {mcq.options.B}
  C: {mcq.options.C}
  D: {mcq.options.D}
  Correct: {mcq.correct}
  Difficulty: {mcq.difficulty}  |  Bloom: {mcq.bloom_level}

Rewrite this MCQ to fix the issue.
Keep the same sub-topic and difficulty level.
Ensure reasoning_process and explanation address all 4 options.
""".strip()


# ── Main public API ───────────────────────────────────────────────────────────

def verify_and_repair(
    mcqs:     list[MCQItem],
    taxonomy: TaxonomySlice,
    label:    str,
) -> list[MCQItem]:
    """
    বিদূষক's adversarial self-critique pass.

    Pattern: Guardrails AI "reask" (Apache 2.0)
    Ask the LLM to audit Sutradhar's output. If issues are found,
    repair them individually before the content reaches triage.

    Now language-aware (WBBSE/WBCHSE → Bengali) and age-aware
    (Class 1-2 → concrete/simple only).

    Returns the same-length list with repaired MCQs substituted.
    Never blocks pipeline — returns originals on verifier failure.
    """
    emit_agent("বিদূষক", f"Auditing {len(mcqs)} MCQs for: {label}")

    # ── Step 1: Audit ─────────────────────────────────────────────────────────
    try:
        verification: MCQBatchVerification = call_llm(
            system         = _VERIFIER_SYSTEM,
            user           = _build_verification_prompt(mcqs, taxonomy, label),
            response_model = MCQBatchVerification,
            temperature    = 0.1,   # low temp — verification needs precision
            max_tokens     = 1024,
            max_retries    = 2,
        )
    except Exception as e:
        emit_progress(f"[বিদূষক] Audit skipped — verifier error: {e}")
        return mcqs  # safe fallback — never block on verifier failure

    if not verification.any_issues:
        emit_agent("বিদূষক", f"✓ All {len(mcqs)} MCQs passed audit")
        return mcqs

    # ── Step 2: Repair flagged MCQs ───────────────────────────────────────────
    issues = {
        v.index: v.issue
        for v in verification.verifications
        if v.verdict == "has_issue" and v.issue
    }
    emit_agent("বিদূষক", f"Found {len(issues)} issue(s) — repairing")

    fixed = list(mcqs)
    prompt_cfg = get_agent_prompt("sutradhar")   # fixer uses sutradhar's creative prompt

    for idx, issue_desc in issues.items():
        if idx >= len(fixed):
            continue
        try:
            repaired: MCQItem = call_llm(
                system         = prompt_cfg.system_prompt,
                user           = _build_fix_prompt(fixed[idx], issue_desc, taxonomy, label),
                response_model = MCQItem,
                temperature    = 0.4,
                max_tokens     = 800,
                max_retries    = 2,
            )
            fixed[idx] = repaired
            emit_progress(f"[বিদূষক] MCQ #{idx} repaired — was: {issue_desc[:80]}")
        except Exception as e:
            emit_progress(f"[বিদূষক] MCQ #{idx} repair failed, keeping original: {e}")

    return fixed
