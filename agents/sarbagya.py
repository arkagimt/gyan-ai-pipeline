"""
সর্বজ্ঞ — The All-Knowing Scout
=================================
Role:   Scout Agent / Knowledge Extractor
Input:  TaxonomySlice + optional raw_text (from PDF or URL)
Output: RawExtract (Pydantic model)

If no source text is provided, সর্বজ্ঞ instructs the LLM to use its
own knowledge for the given taxonomy slice (useful for IT certs, WBCS
topics where LLM knowledge is strong and reliable).
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
from models.schemas import TaxonomySlice, RawExtract


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

def _build_user_prompt(taxonomy: TaxonomySlice, raw_text: str) -> str:
    source_section = (
        f"\n\nSOURCE TEXT (extract only from this):\n{raw_text[:6000]}"
        if raw_text
        else "\n\nNo source text provided. Use your knowledge of the Indian curriculum."
    )

    return f"""
Taxonomy Slice:
  Segment:  {taxonomy.segment.value}
  Label:    {taxonomy.label}
  Count requested: {taxonomy.count} MCQs
{source_section}

Extract educational content for this exact taxonomy slice.

Return ONLY a valid JSON object with this exact structure:
{{
  "key_facts":     ["fact 1", "fact 2", ...],
  "core_concepts": ["concept 1", "concept 2", ...],
  "formulas":      ["formula 1", ...],
  "definitions":   {{"term": "definition", ...}},
  "source_type":   "pdf" | "url" | "llm_knowledge"
}}

Rules:
- key_facts: minimum 8 concrete facts relevant to this topic
- core_concepts: 4–8 named concepts a student must know
- formulas: include ALL relevant formulas (empty list if none)
- definitions: 3–6 key terms with precise definitions
- Do NOT include anything outside this taxonomy slice
- Do NOT hallucinate — if uncertain, omit
""".strip()


# ── Main agent function ───────────────────────────────────────────────────────

def run(taxonomy: TaxonomySlice, raw_text: str = "") -> RawExtract:
    """
    Run সর্বজ্ঞ extraction.
    Retries up to MAX_RETRIES times if JSON parsing fails.
    """
    prompt_cfg = get_agent_prompt("sarbagya")
    emit_agent("সর্বজ্ঞ", f"Extracting content for: {taxonomy.label}")

    user_prompt = _build_user_prompt(taxonomy, raw_text)
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

            extract = RawExtract(
                taxonomy        = taxonomy,
                raw_text        = raw_text[:2000] if raw_text else "(llm knowledge)",
                key_facts       = parsed.get("key_facts", []),
                core_concepts   = parsed.get("core_concepts", []),
                formulas        = parsed.get("formulas", []),
                definitions     = parsed.get("definitions", {}),
                source_type     = parsed.get("source_type", "llm_knowledge"),
                token_count_est = len(user_prompt) // 4,
            )

            emit_agent("সর্বজ্ঞ", f"Extracted {len(extract.key_facts)} facts, {len(extract.core_concepts)} concepts")
            return extract

        except (json.JSONDecodeError, ValidationError, KeyError) as e:
            last_error = e
            emit_progress(f"[সর্বজ্ঞ] Attempt {attempt}/{MAX_RETRIES} failed: {e} — retrying")
            time.sleep(1.5 * attempt)
        except requests.HTTPError as e:
            last_error = e
            emit_progress(f"[সর্বজ্ঞ] Groq HTTP error: {e} — retrying")
            time.sleep(2 * attempt)

    raise RuntimeError(f"সর্বজ্ঞ failed after {MAX_RETRIES} attempts: {last_error}")
