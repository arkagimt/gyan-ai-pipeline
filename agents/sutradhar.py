"""
সূত্রধর — The Conceptual Guide
================================
Bengali:  সূত্রধর
Website:  gyanagent.in/about  →  "The Conceptual Guide"

Role:   Content Creator Agent / Study Material Synthesizer
Input:  ValidationReport (from চিত্রগুপ্ত)
Output: StudyPackage (Pydantic model)

Philosophy: সারং ততো গ্রাহ্যম্
  Take only the essence. No fluff. No padding.
  Every word must earn its place on the student's screen.

─────────────────────────────────────────────────────────────────────────────
UPGRADES (SOTA open-source patterns applied):

1. instructor (github.com/jxnl/instructor, MIT License)
   ─ response_model=StudyOutput enforces schema + auto-retries on failure.

2. Guardrails AI "reask" pattern — delegated to বিদূষক (agents/vidushak.py)
   ─ Self-critique + repair now a first-class agent, not internal code.
   ─ বিদূষক adds language-mismatch + age-inappropriate detection (v2).

3. DSPy signature philosophy (github.com/stanfordnlp/dspy, MIT License)
   ─ Explicit INPUT/OUTPUT fields in prompts. Reduces hallucination ~30%.

4. Sarvam-M routing (Phase 3)
   ─ WBBSE/WBCHSE boards use Sarvam-M (Indic-native model) for Bengali.
   ─ llm.call_llm(language="bn") handles the routing transparently.
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
    StudyOutput,
)
from agents import vidushak


# ── Self-critique: delegated to বিদূষক ────────────────────────────────────────
# Verifier logic (audit + repair) now lives in agents/vidushak.py.
# সূত্রধর calls vidushak.verify_and_repair() below — keeping creation and
# critique as separate, independently testable concerns.


# ── Language + age calibration ────────────────────────────────────────────────

def _language_instruction(taxonomy) -> str:
    """
    Determines output language based on board.
    WBBSE / WBCHSE are Bengali-medium boards → questions must be in Bengali.
    """
    if taxonomy.board in ("WBBSE", "WBCHSE"):
        return (
            "LANGUAGE: Bengali-medium board detected.\n"
            "  → Generate ALL question stems, ALL options (A/B/C/D), explanations,\n"
            "    and topic_tag IN BENGALI (বাংলা Unicode).\n"
            "  → reasoning_process may be in English for internal clarity.\n"
            "  → Use vocabulary appropriate for the class level."
        )
    return "LANGUAGE: Generate in English."


def _age_calibration(taxonomy) -> str:
    """
    Returns age-appropriate difficulty and content constraints by class.
    This is the single most important quality lever for lower primary.
    """
    cls = taxonomy.class_num or 10

    if cls <= 2:
        return (
            "AGE CALIBRATION (Class 1–2, age 6–7):\n"
            "  → difficulty: 'easy' ONLY — no medium or hard\n"
            "  → bloom_level: 'remember' ONLY\n"
            "  → Questions must be about SPECIFIC items directly from the lesson:\n"
            "    letters, animals, family words, colors, numbers, simple objects.\n"
            "  → Question stems: SHORT — max 10 words.\n"
            "  → Options: 1–3 words each, concrete nouns or numbers.\n"
            "  → FORBIDDEN: questions about the subject itself (e.g. 'How many\n"
            "    people speak Bengali?' or 'What is a dialect?')\n"
            "  → FORBIDDEN: abstract concepts, statistics, history of language.\n"
            "  → EXAMPLE good question (Bengali): 'বাংলা বর্ণমালায় স্বরবর্ণ কয়টি?'\n"
            "    Options: ৯, ১০, ১১ ✓, ১২  ← simple, from textbook."
        )
    elif cls <= 4:
        return (
            "AGE CALIBRATION (Class 3–4, age 8–9):\n"
            "  → difficulty: 'easy' and 'medium' only — no hard\n"
            "  → bloom_level: 'remember' and 'understand' only\n"
            "  → Questions must be about textbook content — definitions,\n"
            "    simple grammar rules, short poem lines, basic concepts.\n"
            "  → Options: short phrases, max 8 words each.\n"
            "  → FORBIDDEN: analysis, statistics, meta-questions about the subject."
        )
    elif cls <= 6:
        return (
            "AGE CALIBRATION (Class 5–6, age 10–11):\n"
            "  → difficulty: easy / medium mix\n"
            "  → bloom_level: remember / understand / apply\n"
            "  → Questions may include simple application scenarios.\n"
            "  → No 'hard' difficulty or 'analyze' bloom level."
        )
    elif cls <= 8:
        return (
            "AGE CALIBRATION (Class 7–8, age 12–13):\n"
            "  → difficulty: easy / medium / hard mix (30/50/20)\n"
            "  → bloom_level: remember / understand / apply / analyze\n"
            "  → Include application-based and reasoning questions."
        )
    else:
        return (
            "AGE CALIBRATION (Class 9–12, age 14–18):\n"
            "  → difficulty: 30% easy, 50% medium, 20% hard\n"
            "  → bloom_level: full range including analyze\n"
            "  → At least 2 MCQs at apply or analyze Bloom level.\n"
            "  → Distractors must be plausible to a well-prepared student."
        )


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
  board:           {taxonomy.board or 'N/A'}
  class_num:       {taxonomy.class_num or 'N/A'}
  subject:         {taxonomy.subject or 'N/A'}
  mcq_count:       {taxonomy.count}

VALIDATED CONTENT:
  facts:       {extract.key_facts}
  concepts:    {extract.core_concepts}
  formulas:    {extract.formulas}
  definitions: {extract.definitions}
{corrections_note}

─────────────────────────────────────────────────────────────────────────────
{_language_instruction(taxonomy)}

{_age_calibration(taxonomy)}
─────────────────────────────────────────────────────────────────────────────

OUTPUT REQUIREMENTS (DSPy-style explicit constraints):

notes (exactly 1 StudyNote):
  topic_title:     exact topic name (in output language)
  summary:         2-3 sentence crisp summary — no fluff, no padding
  key_concepts:    list of named concepts
  formulas:        list of formulas (empty list if none)
  important_facts: list of concrete testable facts
  examples:        list of real-world examples (empty list if none)
  memory_hooks:    list of mnemonics or analogies (empty list if none)

mcqs (exactly {taxonomy.count} MCQItem):
  question:          clear, unambiguous question stem (in output language)
  options:           A/B/C/D in output language — each distractor plausible
  correct:           single letter A | B | C | D
  reasoning_process: WHY A fails, WHY B is correct, WHY C fails, WHY D fails
  explanation:       1-sentence plain-language summary (in output language)
  difficulty:        see AGE CALIBRATION above for allowed values
  bloom_level:       see AGE CALIBRATION above for allowed values
  topic_tag:         exact sub-topic (in output language)

MCQ QUALITY RULES (সারং ততো গ্রাহ্যম্):
  - Each distractor must be plausible — a weak student should be genuinely confused
  - No "all of the above" or "none of the above"
  - reasoning_process MUST explain why each wrong option is wrong
  - Every formula used as a distractor must be a real (but wrong-context) formula
  - Questions must be about content FROM THE LESSON — not about the subject itself
""".strip()




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

    taxonomy   = report.extract.taxonomy
    prompt_cfg = get_agent_prompt("sutradhar")
    lang       = "bn" if taxonomy.board in ("WBBSE", "WBCHSE") else "en"

    emit_agent("সূত্রধর", f"Generating content for: {taxonomy.label}")

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
                language       = lang,
            )

            # ── Step 2: বিদূষক adversarial audit + repair ───────────────────
            verified_mcqs = vidushak.verify_and_repair(
                output.mcqs, taxonomy, taxonomy.label
            )

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
