"""
চিত্রগুপ্ত — The Record Keeper
================================
Role:   Triage Agent / Quality Verification Engine
Input:  RawExtract (from সর্বজ্ঞ)
Output: ValidationReport (Pydantic model)

Validates:
  1. Factual correctness for the given board/class/subject
  2. Syllabus alignment — nothing outside scope
  3. Hallucination detection — flags uncertain content
  4. Formula/definition accuracy
  5. Structural completeness (enough data for সূত্রধর to work with)

Upgrade (instructor pattern — github.com/jxnl/instructor, MIT):
  Previously: raw requests.post() + json.loads() + parsed.get() with null risks.
  Now: call_llm(response_model=ValidationOutput) — instructor validates the
  schema and retries. The `corrections: dict` null-bug is gone because
  ValidationOutput declares it as dict with default_factory=dict.

A ValidationReport with is_valid=False stops the pipeline for this slice.
চিত্রগুপ্ত also performs lightweight corrections (e.g. fixing typos in
formula names) rather than outright rejection where possible.
"""

from __future__ import annotations

from instructor.exceptions import InstructorRetryException

from config import (
    MAX_RETRIES, get_agent_prompt, emit_agent, emit_progress,
)
from llm import call_llm
from models.schemas import RawExtract, ValidationReport, ValidationFlag, ValidationOutput


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_user_prompt(extract: RawExtract) -> str:
    taxonomy = extract.taxonomy
    return f"""
INPUT:
  taxonomy:    {taxonomy.label}
  segment:     {taxonomy.segment.value}
  source_type: {extract.source_type}

CONTENT TO VALIDATE:
  Key Facts ({len(extract.key_facts)}):
{chr(10).join(f'    - {f}' for f in extract.key_facts[:15])}

  Core Concepts: {', '.join(extract.core_concepts)}

  Formulas ({len(extract.formulas)}):
{chr(10).join(f'    - {f}' for f in extract.formulas[:10])}

  Definitions ({len(extract.definitions)}):
{chr(10).join(f'    - {k}: {v}' for k, v in list(extract.definitions.items())[:8])}

VALIDATION CHECKS (answer all 5):
  1. Are these facts accurate for {taxonomy.label}?
  2. Are they within the correct syllabus scope (not too advanced/basic)?
  3. Are there hallucinated or uncertain claims?
  4. Are formulas and definitions correct?
  5. Is there sufficient content (min 5 facts, 3 concepts)?

OUTPUT FLAGS (use only these exact string values):
  "factual_error" | "out_of_syllabus" | "hallucination_risk" | "incomplete_content" | "formula_error"

POLICY:
  - Be strict about factual errors and hallucinations
  - Be lenient about minor incompleteness: if 4+ facts exist, pass with incomplete_content flag
  - corrections: map original wrong text to corrected text (empty dict if none)
  - rejection_reason: null if is_valid=true, specific reason string if false
""".strip()


# ── Heuristic pre-checks (no LLM needed) ─────────────────────────────────────

def _heuristic_check(extract: RawExtract) -> tuple[bool, list[ValidationFlag], str | None]:
    """Fast checks before spending an LLM call."""
    flags: list[ValidationFlag] = []
    reason: str | None = None

    if len(extract.key_facts) < 3:
        flags.append(ValidationFlag.incomplete_content)
        reason = f"Only {len(extract.key_facts)} facts extracted — minimum 3 required"
        return False, flags, reason

    if len(extract.core_concepts) < 2:
        flags.append(ValidationFlag.incomplete_content)

    return True, flags, None


# ── Main agent function ───────────────────────────────────────────────────────

def run(extract: RawExtract) -> ValidationReport:
    """
    Run চিত্রগুপ্ত validation.
    1. Fast heuristic check (no LLM).
    2. instructor-validated LLM deep check (no more null corrections bug).
    3. Fallback: pass with hallucination_risk if all LLM attempts fail.
    """
    prompt_cfg = get_agent_prompt("chitragupta")
    emit_agent("চিত্রগুপ্ত", f"Validating content for: {extract.taxonomy.label}")

    # ── 1. Heuristic pre-check ────────────────────────────────────────────────
    heuristic_ok, heuristic_flags, heuristic_reason = _heuristic_check(extract)
    if not heuristic_ok:
        emit_agent("চিত্রগুপ্ত", f"Heuristic FAIL: {heuristic_reason}")
        return ValidationReport(
            extract          = extract,
            is_valid         = False,
            confidence       = 10,
            flags            = heuristic_flags,
            rejection_reason = heuristic_reason,
        )

    # ── 2. LLM deep validation ────────────────────────────────────────────────
    user_prompt = _build_user_prompt(extract)
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            output: ValidationOutput = call_llm(
                system         = prompt_cfg.system_prompt,
                user           = user_prompt,
                response_model = ValidationOutput,
                temperature    = prompt_cfg.temperature,
                max_tokens     = 1024,
                max_retries    = 2,
            )

            # Map string flags to enum (LLM may return any subset)
            valid_flag_values = {f.value for f in ValidationFlag}
            flags: list[ValidationFlag] = [
                ValidationFlag(f) for f in output.flags if f in valid_flag_values
            ] + heuristic_flags

            report = ValidationReport(
                extract          = extract,
                is_valid         = output.is_valid,
                confidence       = output.confidence,
                flags            = flags,
                corrections      = output.corrections,   # always a dict — null bug gone
                rejection_reason = output.rejection_reason,
            )

            status = "✓ VALID" if report.is_valid else "✗ REJECTED"
            emit_agent("চিত্রগুপ্ত", f"{status} — confidence {report.confidence}% — flags: {[f.value for f in report.flags]}")
            return report

        except InstructorRetryException as e:
            last_error = e
            emit_progress(f"[চিত্রগুপ্ত] Attempt {attempt}/{MAX_RETRIES} — instructor validation failed: {e}")
        except Exception as e:
            last_error = e
            emit_progress(f"[চিত্রগুপ্ত] Attempt {attempt}/{MAX_RETRIES} — error: {e}")

    # ── 3. Fallback: pass with warning rather than block pipeline ─────────────
    emit_agent("চিত্রগুপ্ত", f"LLM validation failed after {MAX_RETRIES} attempts — passing with warning flag")
    return ValidationReport(
        extract          = extract,
        is_valid         = True,
        confidence       = 50,
        flags            = [ValidationFlag.hallucination_risk] + heuristic_flags,
        rejection_reason = None,
    )
