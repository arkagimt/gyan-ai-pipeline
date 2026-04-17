"""
LLM Client — Multi-provider, Instructor-patched
================================================
Single source of truth for all LLM calls in the pipeline.

Providers:
  • Groq / Llama-3.3-70b  — default for all English content
  • Sarvam-M               — routed for Bengali content (WBBSE / WBCHSE boards)
                             Sarvam is purpose-built for Indic languages;
                             dramatically better Bengali than any English-first LLM.

Routing:
  call_llm(..., language="bn") → Sarvam-M (with Groq fallback on failure)
  call_llm(...)                → Groq / Llama-3.3-70b (default)

Observability:
  Set PHOENIX_ENDPOINT env var to enable Arize Phoenix tracing.
  All LLM calls are auto-instrumented via OpenInference.
  No-op if the env var is absent or deps not installed.

References:
  github.com/jxnl/instructor   (MIT)  — structured output + auto-retry
  github.com/stanfordnlp/dspy  (MIT)  — signature philosophy
  sarvam.ai                           — Indic-native model API (OpenAI-compatible)
  arize-phoenix.readthedocs.io (BSL)  — LLM observability
"""

from __future__ import annotations
import functools
from typing import TypeVar

import instructor
from groq import Groq
from instructor.exceptions import InstructorRetryException

from config import (
    GROQ_API_KEY, GROQ_MODEL,
    SARVAM_API_KEY, SARVAM_MODEL, SARVAM_BASE_URL,
    PHOENIX_ENDPOINT,
    emit_progress,
)

T = TypeVar("T")


# ── Phoenix tracing (optional) ────────────────────────────────────────────────

def _setup_tracing() -> None:
    """
    Instruments all LLM calls with Arize Phoenix if PHOENIX_ENDPOINT is set.
    Completely silent / no-op if:
      • PHOENIX_ENDPOINT env var is not set
      • arize-phoenix-otel or openinference packages are not installed
    Install: pip install arize-phoenix-otel openinference-instrumentation-groq
    """
    if not PHOENIX_ENDPOINT:
        return
    try:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{PHOENIX_ENDPOINT}/v1/traces"))
        )

        # Groq instrumentation (default LLM + Llama Guard 3 safety calls)
        instrumented: list[str] = []
        try:
            from openinference.instrumentation.groq import GroqInstrumentor
            GroqInstrumentor().instrument(tracer_provider=provider)
            instrumented.append("groq")
        except ImportError:
            pass

        # OpenAI instrumentation covers Sarvam-M (Bengali routing uses the
        # OpenAI-compatible client against api.sarvam.ai/v1). Without this,
        # the entire Bengali traffic — the whole point of Sarvam — is invisible.
        try:
            from openinference.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=provider)
            instrumented.append("openai/sarvam")
        except ImportError:
            pass

        if instrumented:
            emit_progress(
                f"[tracing] 🔭 Phoenix active → {PHOENIX_ENDPOINT} "
                f"(instrumented: {', '.join(instrumented)})"
            )
        else:
            emit_progress(
                "[tracing] Phoenix endpoint set but no instrumentors installed — skipping. "
                "Install: pip install openinference-instrumentation-groq openinference-instrumentation-openai"
            )
    except ImportError:
        emit_progress(
            "[tracing] Phoenix deps not installed — skipping. "
            "To enable: pip install arize-phoenix-otel "
            "openinference-instrumentation-groq openinference-instrumentation-openai"
        )


_tracing_initialized = False


def _ensure_tracing() -> None:
    global _tracing_initialized
    if not _tracing_initialized:
        _setup_tracing()
        _tracing_initialized = True


# ── Groq instructor client (singleton) ───────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _get_groq_client() -> instructor.Instructor:
    """
    Instructor-patched Groq client.
    Mode.JSON = Groq native JSON mode + Pydantic schema injection + retry.
    """
    return instructor.from_groq(
        Groq(api_key=GROQ_API_KEY),
        mode=instructor.Mode.JSON,
    )


# ── Sarvam instructor client (singleton) ─────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _get_sarvam_client() -> instructor.Instructor | None:
    """
    Instructor-patched Sarvam client via OpenAI-compatible endpoint.
    Returns None if SARVAM_API_KEY is not configured.

    Sarvam-M is purpose-built for Indic languages including Bengali.
    Produces dramatically better Bengali MCQs than Llama-3.3-70B.
    See: https://www.sarvam.ai/
    """
    if not SARVAM_API_KEY:
        return None
    try:
        from openai import OpenAI
        return instructor.from_openai(
            OpenAI(api_key=SARVAM_API_KEY, base_url=SARVAM_BASE_URL),
            mode=instructor.Mode.JSON,
        )
    except Exception as e:
        emit_progress(f"[llm] Sarvam client init failed: {e} — will use Groq fallback")
        return None


# ── Main call function ────────────────────────────────────────────────────────

def call_llm(
    system:         str,
    user:           str,
    response_model: type[T],
    temperature:    float = 0.3,
    max_tokens:     int   = 4096,
    max_retries:    int   = 3,
    language:       str   = "en",   # "bn" → route to Sarvam-M for Bengali
) -> T:
    """
    Unified LLM call with automatic provider routing.

    language="bn"  → tries Sarvam-M first (Indic-native), falls back to Groq.
    language="en"  → uses Groq / Llama-3.3-70b directly.

    On each attempt:
      1. Sends system + user messages with JSON mode.
      2. instructor extracts JSON and validates against response_model.
      3. If validation fails, instructor sends the Pydantic error back
         to the LLM for self-correction.
      4. After max_retries exhausted, raises InstructorRetryException.
    """
    _ensure_tracing()

    # ── Bengali routing → Sarvam-M ────────────────────────────────────────────
    if language == "bn":
        sarvam = _get_sarvam_client()
        if sarvam:
            try:
                return sarvam.chat.completions.create(
                    model          = SARVAM_MODEL,
                    messages       = [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    response_model = response_model,
                    temperature    = temperature,
                    max_tokens     = max_tokens,
                    max_retries    = max_retries,
                )
            except Exception as e:
                emit_progress(
                    f"[llm] Sarvam-M failed ({type(e).__name__}: {str(e)[:80]}) "
                    f"— falling back to Groq"
                )
        else:
            emit_progress("[llm] SARVAM_API_KEY not set — using Groq for Bengali content")

    # ── Default → Groq / Llama ────────────────────────────────────────────────
    client = _get_groq_client()
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
