"""
সর্বজ্ঞ — The Scout & Ingestor
================================
Bengali:  সর্বজ্ঞ
Website:  gyanagent.in/about  →  "The Scout & Ingestor"

Role:   Scout Agent / Knowledge Extractor
Input:  TaxonomySlice + optional raw_text (from PDF or URL)
Output: RawExtract (Pydantic model)

Upgrade (instructor pattern — github.com/jxnl/instructor, MIT):
  Previously used raw requests.post() + json.loads() + manual parsing.
  Now uses call_llm() with response_model=ExtractOutput:
    - instructor injects Pydantic schema into the prompt automatically
    - validates the response against ExtractOutput (min 3 facts, 2 concepts)
    - on validation failure, sends the error back to the LLM and retries
    - zero silent failures: either a valid ExtractOutput or an exception

DSPy signature philosophy (github.com/stanfordnlp/dspy, MIT):
  Prompt now declares explicit INPUT fields and OUTPUT constraints
  rather than open-ended instructions, reducing hallucination.
"""

from __future__ import annotations

from instructor.exceptions import InstructorRetryException

from config import (
    MAX_RETRIES, get_agent_prompt, emit_agent, emit_progress,
)
from llm import call_llm
from models.schemas import TaxonomySlice, RawExtract, ExtractOutput


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_user_prompt(taxonomy: TaxonomySlice, raw_text: str) -> str:
    source_section = (
        f"\n\nSOURCE TEXT (extract ONLY from this — do not add external knowledge):\n{raw_text[:6000]}"
        if raw_text
        else "\n\nNo source text provided. Use your own knowledge of the Indian curriculum."
    )

    return f"""
INPUT:
  segment:  {taxonomy.segment.value}
  label:    {taxonomy.label}
  mcq_count_needed: {taxonomy.count}
{source_section}

OUTPUT REQUIREMENTS (DSPy-style explicit constraints):
  key_facts     → minimum 8 concrete, testable facts about this topic
  core_concepts → 4–8 named concepts the student MUST know
  formulas      → every relevant formula / equation (empty list if none)
  definitions   → 3–6 key terms with precise, curriculum-accurate definitions
  source_type   → "pdf" | "url" | "llm_knowledge"

QUALITY RULES:
  - Do NOT include anything outside this exact taxonomy slice
  - Do NOT hallucinate — if uncertain about a fact, omit it
  - facts must be concrete and testable (not vague summaries)
  - definitions must match {taxonomy.segment.value} curriculum level
""".strip()


# ── Main agent function ───────────────────────────────────────────────────────

def run(taxonomy: TaxonomySlice, raw_text: str = "") -> RawExtract:
    """
    Run সর্বজ্ঞ extraction.
    instructor handles schema validation + retry internally.
    Outer loop catches network/API errors only.
    """
    prompt_cfg = get_agent_prompt("sarbagya")
    emit_agent("সর্বজ্ঞ", f"Extracting content for: {taxonomy.label}")

    lang        = "bn" if taxonomy.board in ("WBBSE", "WBCHSE") else "en"
    user_prompt = _build_user_prompt(taxonomy, raw_text)
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            output: ExtractOutput = call_llm(
                system         = prompt_cfg.system_prompt,
                user           = user_prompt,
                response_model = ExtractOutput,
                temperature    = prompt_cfg.temperature,
                max_tokens     = prompt_cfg.max_tokens,
                max_retries    = 3,
                language       = lang,
            )

            extract = RawExtract(
                taxonomy        = taxonomy,
                raw_text        = raw_text[:2000] if raw_text else "(llm knowledge)",
                key_facts       = output.key_facts,
                core_concepts   = output.core_concepts,
                formulas        = output.formulas,
                definitions     = output.definitions,
                source_type     = output.source_type,
                token_count_est = len(user_prompt) // 4,
            )

            emit_agent("সর্বজ্ঞ", f"Extracted {len(extract.key_facts)} facts, {len(extract.core_concepts)} concepts")
            return extract

        except InstructorRetryException as e:
            last_error = e
            emit_progress(f"[সর্বজ্ঞ] Attempt {attempt}/{MAX_RETRIES} — instructor validation failed: {e}")
        except Exception as e:
            last_error = e
            emit_progress(f"[সর্বজ্ঞ] Attempt {attempt}/{MAX_RETRIES} — error: {e}")

    raise RuntimeError(f"সর্বজ্ঞ failed after {MAX_RETRIES} attempts: {last_error}")
