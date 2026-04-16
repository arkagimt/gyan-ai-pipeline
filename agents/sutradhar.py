"""
সূত্রধর — The Storyteller
===========================
Role:   Content Creator Agent / Study Material Synthesizer
Input:  ValidationReport (from চিত্রগুপ্ত)
Output: StudyPackage (Pydantic model)

Philosophy: সারং ততো গ্রাহ্যম্
  Take only the essence. No fluff. No padding.
  Every word must earn its place on the student's screen.

Generates:
  - StudyNote: crisp summary, key concepts, formulas, memory hooks
  - MCQItem[]: conceptual MCQs with chain-of-thought explanations

MCQ quality bar:
  - Tests UNDERSTANDING, not trivia recall
  - Each distractor (wrong option) is plausible — not obviously wrong
  - Explanation walks through the reasoning, not just "the answer is X"
  - Bloom's taxonomy level tagged (remember/understand/apply/analyze)
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
from models.schemas import (
    ValidationReport, StudyPackage, StudyNote, MCQItem, MCQOption,
)


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

def _build_user_prompt(report: ValidationReport) -> str:
    extract  = report.extract
    taxonomy = extract.taxonomy

    corrections_note = ""
    if report.corrections:
        corrections_note = f"\nNote corrections made during validation: {report.corrections}"

    return f"""
Create study material for Gyan AI students.

Taxonomy:   {taxonomy.label}
Segment:    {taxonomy.segment.value}
MCQ count requested: {taxonomy.count}

Validated content:
  Facts:    {extract.key_facts}
  Concepts: {extract.core_concepts}
  Formulas: {extract.formulas}
  Definitions: {extract.definitions}
{corrections_note}

Return ONLY valid JSON with this exact structure:
{{
  "notes": [
    {{
      "topic_title":     "exact topic name",
      "summary":         "2-3 sentence crisp summary — no fluff",
      "key_concepts":    ["concept 1", "concept 2", ...],
      "formulas":        ["formula 1", ...],
      "important_facts": ["fact 1", "fact 2", ...],
      "examples":        ["example 1", ...],
      "memory_hooks":    ["mnemonic or analogy", ...]
    }}
  ],
  "mcqs": [
    {{
      "question":          "Clear, unambiguous question",
      "options":           {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct":           "A" | "B" | "C" | "D",
      "reasoning_process": "Step-by-step: First, consider A — it is wrong because... B is correct because... C fails because... D fails because...",
      "explanation":       "One sentence: the correct answer in plain language",
      "difficulty":        "easy" | "medium" | "hard",
      "bloom_level":       "remember" | "understand" | "apply" | "analyze",
      "topic_tag":         "sub-topic this tests"
    }}
  ]
}}

MCQ rules (सारं ततो ग्राह्यम्):
- Generate exactly {taxonomy.count} MCQs
- Each distractor must be plausible — a weak student should be confused
- Avoid "all of the above" / "none of the above"
- Explanation must be 2-3 sentences of genuine reasoning
- Mix difficulty: ~30% easy, ~50% medium, ~20% hard
- At least 2 MCQs at apply/analyze Bloom level
- One StudyNote covering the core topic (can have sub-sections)
""".strip()


# ── Parse and validate MCQ list ───────────────────────────────────────────────

def _parse_mcqs(raw_list: list[dict]) -> list[MCQItem]:
    valid: list[MCQItem] = []
    for item in raw_list:
        try:
            # Support LLM returning explanation only (no reasoning_process) — graceful fallback
            explanation       = str(item.get("explanation", ""))
            reasoning_process = str(item.get("reasoning_process") or item.get("chain_of_thought") or explanation)
            mcq = MCQItem(
                question          = str(item["question"]),
                options           = MCQOption(**item["options"]),
                correct           = str(item["correct"]).upper(),
                reasoning_process = reasoning_process,
                explanation       = explanation,
                difficulty        = str(item.get("difficulty", "medium")),
                bloom_level       = str(item.get("bloom_level", "understand")),
                topic_tag         = str(item.get("topic_tag", "")),
            )
            valid.append(mcq)
        except (ValidationError, KeyError, TypeError):
            continue  # skip malformed MCQs silently
    return valid


def _parse_notes(raw_list: list[dict]) -> list[StudyNote]:
    valid: list[StudyNote] = []
    for item in raw_list:
        try:
            note = StudyNote(
                topic_title     = str(item["topic_title"]),
                summary         = str(item.get("summary", "")),
                key_concepts    = list(item.get("key_concepts", [])),
                formulas        = list(item.get("formulas", [])),
                important_facts = list(item.get("important_facts", [])),
                examples        = list(item.get("examples", [])),
                memory_hooks    = list(item.get("memory_hooks", [])),
            )
            valid.append(note)
        except (ValidationError, KeyError, TypeError):
            continue
    return valid


# ── Main agent function ───────────────────────────────────────────────────────

def run(report: ValidationReport) -> StudyPackage:
    """
    Run সূত্রধর content generation.
    Only runs if চিত্রগুপ্ত approved the content (is_valid=True).
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
            raw_json = _call_groq(
                system      = prompt_cfg.system_prompt,
                user        = user_prompt,
                temperature = prompt_cfg.temperature,
                max_tokens  = prompt_cfg.max_tokens,
            )

            parsed = json.loads(raw_json)

            mcqs  = _parse_mcqs(parsed.get("mcqs", []))
            notes = _parse_notes(parsed.get("notes", []))

            if not mcqs:
                raise ValueError("No valid MCQs parsed from সূত্রধর output")

            package = StudyPackage(
                taxonomy = report.extract.taxonomy,
                notes    = notes,
                mcqs     = mcqs,
                metadata = {
                    "confidence":   report.confidence,
                    "flags":        [f.value for f in report.flags],
                    "source_type":  report.extract.source_type,
                    "attempt":      attempt,
                },
            )

            emit_agent("সূত্রধর", f"Generated {len(mcqs)} MCQs + {len(notes)} study note(s)")
            return package

        except (json.JSONDecodeError, ValidationError, ValueError, KeyError) as e:
            last_error = e
            emit_progress(f"[সূত্রধর] Attempt {attempt}/{MAX_RETRIES} failed: {e} — retrying")
            time.sleep(1.5 * attempt)
        except requests.HTTPError as e:
            last_error = e
            emit_progress(f"[সূত্রধর] Groq HTTP error: {e} — retrying")
            time.sleep(2 * attempt)

    raise RuntimeError(f"সূত্রধর failed after {MAX_RETRIES} attempts: {last_error}")
