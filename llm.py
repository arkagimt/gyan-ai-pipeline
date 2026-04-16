"""
LLM Client — Instructor-patched Groq
======================================
Single source of truth for all LLM calls in the pipeline.

Replaces the per-agent raw requests.post() pattern with a typed,
validated, auto-retrying client.

Inspired by:
  github.com/jxnl/instructor   (MIT License)
  — Structured LLM outputs with Pydantic validation + automatic retry.
    When the LLM returns malformed JSON or fails a Pydantic validator,
    instructor feeds the validation error back to the LLM and retries.
    Zero silent failures — either you get a valid model or an exception.

  github.com/guardrails-ai/guardrails   (Apache 2.0)
  — "Reask" pattern: the LLM is asked to fix its own output.
    We borrow this concept in সূত্রধর's _verify_mcqs() step.

  github.com/stanfordnlp/dspy   (MIT)
  — Signature philosophy: describe inputs + outputs explicitly,
    not just instructions. Applied in our prompt builders.
"""

from __future__ import annotations
import functools
from typing import TypeVar

import instructor
from groq import Groq
from instructor.exceptions import InstructorRetryException

from config import GROQ_API_KEY, GROQ_MODEL, emit_progress

T = TypeVar("T")


# ── Instructor-patched Groq client (singleton) ────────────────────────────────

@functools.lru_cache(maxsize=1)
def _get_client() -> instructor.Instructor:
    """
    Returns an instructor-patched Groq client.
    instructor.Mode.JSON = uses Groq's native JSON mode (same as response_format: json_object),
    but adds Pydantic schema injection + validation retry loop on top.
    """
    return instructor.from_groq(
        Groq(api_key=GROQ_API_KEY),
        mode=instructor.Mode.JSON,
    )


# ── Main call function ────────────────────────────────────────────────────────

def call_llm(
    system:         str,
    user:           str,
    response_model: type[T],
    temperature:    float = 0.3,
    max_tokens:     int   = 4096,
    max_retries:    int   = 3,
) -> T:
    """
    Call Groq with instructor's structured output layer.

    On each attempt:
      1. Sends system + user messages to Groq with JSON mode.
      2. instructor extracts the JSON and validates against response_model.
      3. If validation fails, instructor sends the Pydantic error back to
         the LLM as a follow-up message: "Please fix these errors: ..."
      4. After max_retries exhausted, raises InstructorRetryException.

    Callers should catch InstructorRetryException for graceful fallback.
    """
    client = _get_client()
    return client.chat.completions.create(
        model          = GROQ_MODEL,
        messages       = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        response_model = response_model,
        temperature    = temperature,
        max_tokens     = max_tokens,
        max_retries    = max_retries,
    )
