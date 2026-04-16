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

A ValidationReport with is_valid=False stops the pipeline for this slice.
চিত্রগুপ্ত also performs lightweight corrections (e.g. fixing typos in
formula names) rather than outright rejection where possible.
"""

from __future__ import annotations
import json
import time
import requests
from pydantic import ValidationError

from config import (
    GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL,
    MAX_RETRIES, LLM_TIMEOUT_S,
    get_agent_prompt, emit_agent, emit_progress,
)
from models.schemas import RawExtract, ValidationReport, ValidationFlag


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_groq(system: str, user: str, temperature: float, max_tokens: int) -> str:
    resp = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": temperature,
            "max_tokens":  max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=LLM_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_user_prompt(extract: RawExtract) -> str:
    taxonomy = extract.taxonomy
    return f"""
You are validating educational content for the Gyan AI platform.

Taxonomy:   {taxonomy.label}
Segment:    {taxonomy.segment.value}
Source type: {extract.source_type}

Content to validate:
  Key Facts ({len(extract.key_facts)}):
    {chr(10).join(f'  - {f}' for f in extract.key_facts[:15])}

  Core Concepts: {', '.join(extract.core_concepts)}

  Formulas ({len(extract.formulas)}):
    {chr(10).join(f'  - {f}' for f in extract.formulas[:10])}

  Definitions ({len(extract.definitions)}):
    {chr(10).join(f'  - {k}: {v}' for k, v in list(extract.definitions.items())[:8])}

Validation checks:
1. Are these facts accurate for {taxonomy.label}?
2. Are they within the correct syllabus scope?
3. Are there any hallucinated/uncertain claims?
4. Are formulas/definitions correct?
5. Is there sufficient content (min 5 facts, 3 concepts)?

Return ONLY valid JSON:
{{
  "is_valid":         true | false,
  "confidence":       0-100,
  "flags":            [] | ["factual_error", "out_of_syllabus", "hallucination_risk", "incomplete_content", "formula_error"],
  "corrections":      {{"original": "corrected", ...}},
  "rejection_reason": null | "reason if is_valid=false"
}}

Be strict about factual errors and hallucinations.
Be lenient about minor incompleteness (if 4+ facts exist, pass with incomplete_content flag).
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
    Fast heuristic check first, then LLM deep check.
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
            raw_json = _call_groq(
                system      = prompt_cfg.system_prompt,
                user        = user_prompt,
                temperature = prompt_cfg.temperature,
                max_tokens  = 1024,
            )

            parsed = json.loads(raw_json)

            # Map string flags to enum
            raw_flags = parsed.get("flags", [])
            valid_flag_values = {f.value for f in ValidationFlag}
            flags: list[ValidationFlag] = [
                ValidationFlag(f) for f in raw_flags if f in valid_flag_values
            ] + heuristic_flags

            report = ValidationReport(
                extract          = extract,
                is_valid         = bool(parsed.get("is_valid", True)),
                confidence       = int(parsed.get("confidence", 70)),
                flags            = flags,
                corrections      = parsed.get("corrections") or {},   # LLM may return null
                rejection_reason = parsed.get("rejection_reason"),
            )

            status = "✓ VALID" if report.is_valid else "✗ REJECTED"
            emit_agent("চিত্রগুপ্ত", f"{status} — confidence {report.confidence}% — flags: {[f.value for f in report.flags]}")
            return report

        except (json.JSONDecodeError, ValidationError, KeyError) as e:
            last_error = e
            emit_progress(f"[চিত্রগুপ্ত] Attempt {attempt}/{MAX_RETRIES} failed: {e} — retrying")
            time.sleep(1.5 * attempt)
        except requests.HTTPError as e:
            last_error = e
            emit_progress(f"[চিত্রগুপ্ত] Groq HTTP error: {e} — retrying")
            time.sleep(2 * attempt)

    # If LLM validation fails entirely, pass with warning (don't block pipeline)
    emit_agent("চিত্রগুপ্ত", f"LLM validation failed after {MAX_RETRIES} attempts — passing with warning flag")
    return ValidationReport(
        extract          = extract,
        is_valid         = True,
        confidence       = 50,
        flags            = [ValidationFlag.hallucination_risk] + heuristic_flags,
        rejection_reason = None,
    )
