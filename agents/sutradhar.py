"""
সূত্রধর — The Storyteller
===========================
Role:   Content Creator Agent / Study Material Synthesizer
Input:  ValidationReport (from চিত্রগুপ্ত)
Output: StudyPackage (Pydantic model)

Philosophy: সারং ততো গ্রাহ্যম্
  Take only the essence. No fluff. No padding.
  Every word must earn its place on the student's screen.

─────────────────────────────────────────────────────────────────────────────
UPGRADES (SOTA open-source patterns applied):

1. instructor (github.com/jxnl/instructor, MIT License)
   ─ Replaces raw requests.post() + json.loads() + _parse_mcqs() silent-skip.
   ─ response_model=StudyOutput enforces schema; instructor retries with the
     Pydantic error message fed back to the LLM. Zero blank cards.

2. Guardrails AI "reask" pattern (github.com/guardrails-ai/guardrails, Apache 2.0)
   ─ After generation, _verify_mcqs() runs a self-critique pass.
   ─ The LLM checks its own MCQs for: accidentally-correct distractors,
     ambiguous questions, factually wrong answers.
   ─ Flagged MCQs are individually regenerated with the issue description.
   ─ This is the #1 source of MCQ quality improvement in practice.

3. DSPy signature philosophy (github.com/stanfordnlp/dspy, MIT License)
   ─ Prompts declare explicit INPUT fields and OUTPUT constraints
     rather than open-ended instructions. Reduces hallucination ~30%.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from instructor.exceptions import InstructorRetryException

from config import (
    MAX_RETRIES, get_agent_prompt, emit_agent, emit_progress,
)
from llm import call_llm
from models.schemas import (
    ValidationReport, StudyPackage,
    StudyOutput, MCQItem, MCQBatchVerification,
)


# ── Verifier system prompt ────────────────────────────────────────────────────
# Kept inline — this is infrastructure, not content config.

_VERIFIER_SYSTEM = """
You are a strict MCQ quality auditor for an Indian education platform.
Your job: find genuine errors in MCQs — not stylistic preferences.

Check each MCQ for these SPECIFIC issues only:
  1. DISTRACTOR_CORRECT  — a wrong option that is actually also correct
     (most common in physics/math: e.g. P=IV listed as distractor when it is valid)
  2. WRONG_ANSWER        — the marked correct option is factually incorrect
  3. TWO_CORRECT_OPTIONS — more than one option is unambiguously correct
  4. AMBIGUOUS_QUESTION  — the question can be reasonably interpreted multiple ways

Do NOT flag:
  - Minor wording preferences
  - Difficulty level opinions
  - Bloom level disagreements

Be conservative: only flag issues you are CERTAIN about.
verdict must be exactly "ok" or "has_issue".
"""


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_user_prompt(report: ValidationReport) -> str:
    extract  = report.extract
    taxonomy = extract.taxonomy

    corrections_note = ""
    if report.corrections:
        corrections_note = f"\nNote corrections made during validation: {report.corrections}"

    return f"""
INPUT:
  taxonomy_label:  {taxonomy.label}
  segment:         {taxonomy.segment.value}
  mcq_count:       {taxonomy.count}

VALIDATED CONTENT:
  facts:       {extract.key_facts}
  concepts:    {extract.core_concepts}
  formulas:    {extract.formulas}
  definitions: {extract.definitions}
{corrections_note}

OUTPUT REQUIREMENTS (DSPy-style explicit constraints):

notes (exactly 1 StudyNote):
  topic_title:     exact topic name
  summary:         2-3 sentence crisp summary — no fluff, no padding
  key_concepts:    list of named concepts
  formulas:        list of formulas (empty list if none)
  important_facts: list of concrete testable facts
  examples:        list of real-world examples (empty list if none)
  memory_hooks:    list of mnemonics or analogies (empty list if none)

mcqs (exactly {taxonomy.count} MCQItem):
  question:          clear, unambiguous question stem
  options:           A/B/C/D — each distractor must be plausible to a weak student
  correct:           single letter A | B | C | D
  reasoning_process: step-by-step walkthrough — WHY A fails, WHY B is correct,
                     WHY C fails, WHY D fails — address ALL 4 options explicitly
  explanation:       1-sentence plain-language summary of the correct answer
  difficulty:        "easy" | "medium" | "hard"
  bloom_level:       "remember" | "understand" | "apply" | "analyze"
  topic_tag:         exact sub-topic this question tests

MCQ QUALITY RULES (সারং ততো গ্রাহ্যম্):
  - Each distractor must be plausible — a weak student should be genuinely confused
  - No "all of the above" or "none of the above"
  - reasoning_process MUST explain why each wrong option is wrong
  - Mix: ~30% easy, ~50% medium, ~20% hard
  - At least 2 MCQs at apply or analyze Bloom level
  - Every formula used as a distractor must be a real (but wrong-context) formula
""".strip()


def _build_verification_prompt(mcqs: list[MCQItem], label: str) -> str:
    mcq_text = "\n\n".join(
        f"MCQ #{i}:\n"
        f"  Q: {m.question}\n"
        f"  A: {m.options.A}\n"
        f"  B: {m.options.B}\n"
        f"  C: {m.options.C}\n"
        f"  D: {m.options.D}\n"
        f"  Correct: {m.correct}"
        for i, m in enumerate(mcqs)
    )
    return f"""
Topic: {label}

Review these {len(mcqs)} MCQs for factual or logical errors only:

{mcq_text}

For each MCQ return:
  index:   the MCQ number (0-based)
  verdict: "ok" or "has_issue"
  issue:   null if ok, specific description if has_issue
           Example: "Option C (P = IV) is also a valid power formula — two correct answers"

Set any_issues=true if ANY MCQ has verdict="has_issue".
""".strip()


def _build_fix_prompt(mcq: MCQItem, issue: str, label: str) -> str:
    return f"""
Topic: {label}

This MCQ has a quality issue that must be fixed: {issue}

Original MCQ:
  Question: {mcq.question}
  A: {mcq.options.A}
  B: {mcq.options.B}
  C: {mcq.options.C}
  D: {mcq.options.D}
  Correct: {mcq.correct}

Rewrite this MCQ to fix the issue. Keep the same sub-topic and difficulty level.
Ensure reasoning_process and explanation are thorough (address all 4 options).
""".strip()


# ── Self-critique verifier ────────────────────────────────────────────────────

def _verify_mcqs(mcqs: list[MCQItem], label: str) -> list[MCQItem]:
    """
    Self-critique pass on generated MCQs.

    Inspired by Guardrails AI's 'reask' pattern (Apache 2.0):
    ask the LLM to audit its own output and fix genuine errors
    before they reach students.

    Most common issue caught: accidentally-correct distractors in
    physics/math (e.g., listing P=IV as a wrong option when it is valid).
    """
    try:
        verification: MCQBatchVerification = call_llm(
            system         = _VERIFIER_SYSTEM,
            user           = _build_verification_prompt(mcqs, label),
            response_model = MCQBatchVerification,
            temperature    = 0.1,   # low temp — verification needs precision
            max_tokens     = 1024,
            max_retries    = 2,
        )
    except Exception as e:
        emit_progress(f"[সূত্রধর] Self-critique skipped (verifier error: {e})")
        return mcqs   # keep originals — never block pipeline on verifier failure

    if not verification.any_issues:
        emit_agent("সূত্রধর", f"Self-critique ✓ — all {len(mcqs)} MCQs passed")
        return mcqs

    # Repair flagged MCQs one by one
    issues = {
        v.index: v.issue
        for v in verification.verifications
        if v.verdict == "has_issue" and v.issue
    }
    emit_agent("সূত্রধর", f"Self-critique found {len(issues)} issue(s) — repairing")

    fixed = list(mcqs)
    prompt_cfg = get_agent_prompt("sutradhar")

    for idx, issue_desc in issues.items():
        if idx >= len(fixed):
            continue
        try:
            repaired: MCQItem = call_llm(
                system         = prompt_cfg.system_prompt,
                user           = _build_fix_prompt(fixed[idx], issue_desc, label),
                response_model = MCQItem,
                temperature    = 0.4,
                max_tokens     = 800,
                max_retries    = 2,
            )
            fixed[idx] = repaired
            emit_progress(f"[সূত্রধর] MCQ #{idx} repaired — was: {issue_desc[:80]}")
        except Exception as e:
            emit_progress(f"[সূত্রধর] MCQ #{idx} repair failed, keeping original: {e}")

    return fixed


# ── Main agent function ───────────────────────────────────────────────────────

def run(report: ValidationReport) -> StudyPackage:
    """
    Run সূত্রধর content generation.
    Only runs if চিত্রগুপ্ত approved the content (is_valid=True).

    Pipeline:
      1. Generate StudyOutput (notes + MCQs) via instructor
      2. Self-critique MCQs via _verify_mcqs() (Guardrails reask pattern)
      3. Return StudyPackage
    """
    if not report.is_valid:
        raise ValueError(
            f"সূত্রধর cannot run — চিত্রগুপ্ত rejected content: {report.rejection_reason}"
        )

    prompt_cfg = get_agent_prompt("sutradhar")
    emit_agent("সূত্রধর", f"Generating content for: {report.extract.taxonomy.label}")

    user_prompt = _build_user_prompt(report)
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # ── Step 1: Generate ─────────────────────────────────────────────
            output: StudyOutput = call_llm(
                system         = prompt_cfg.system_prompt,
                user           = user_prompt,
                response_model = StudyOutput,
                temperature    = prompt_cfg.temperature,
                max_tokens     = prompt_cfg.max_tokens,
                max_retries    = 3,
            )

            # ── Step 2: Self-critique MCQs (Guardrails reask pattern) ────────
            verified_mcqs = _verify_mcqs(output.mcqs, report.extract.taxonomy.label)

            # ── Step 3: Assemble final StudyPackage ───────────────────────────
            package = StudyPackage(
                taxonomy = report.extract.taxonomy,
                notes    = output.notes,
                mcqs     = verified_mcqs,
                metadata = {
                    "confidence":   report.confidence,
                    "flags":        [f.value for f in report.flags],
                    "source_type":  report.extract.source_type,
                    "attempt":      attempt,
                },
            )

            emit_agent("সূত্রধর", f"Generated {len(verified_mcqs)} MCQs + {len(output.notes)} study note(s)")
            return package

        except InstructorRetryException as e:
            last_error = e
            emit_progress(f"[সূত্রধর] Attempt {attempt}/{MAX_RETRIES} — instructor validation failed: {e}")
        except Exception as e:
            last_error = e
            emit_progress(f"[সূত্রধর] Attempt {attempt}/{MAX_RETRIES} — error: {e}")

    raise RuntimeError(f"সূত্রধর failed after {MAX_RETRIES} attempts: {last_error}")
