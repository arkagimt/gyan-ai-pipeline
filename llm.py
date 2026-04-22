"""
LLM Client — Multi-provider, Instructor-patched, Router-based
=============================================================
Single source of truth for all LLM calls in the pipeline.

Providers (today):
  • Groq / Llama-3.3-70b  — default for English + fallback for everything
  • Sarvam-M               — routed for Bengali content (WBBSE / WBCHSE boards)
                             Sarvam is purpose-built for Indic languages;
                             dramatically better Bengali than any English-first LLM.

Providers (ready to register — not wired by default):
  • Anthropic Claude       — add via register_provider("anthropic", ...)
  • OpenAI GPT-4o          — add via register_provider("openai", ...)

Router (Phase 19):
  call_llm(..., language="bn")     → route("bn") → [Sarvam, Groq] in order
  call_llm(..., model_hint="groq") → route(model_hint="groq") → [Groq] only
  call_llm(...)                    → route(default) → [Groq]

Each provider in the returned chain is tried until one succeeds.
Registering a new provider is ONE function call — no edits to call_llm.

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
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, TypeVar

import instructor
from groq import Groq
from instructor.exceptions import InstructorRetryException

from config import (
    GROQ_API_KEY, GROQ_MODEL,
    SARVAM_API_KEY, SARVAM_MODEL, SARVAM_BASE_URL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    PHOENIX_ENDPOINT,
    emit_progress,
)

T = TypeVar("T")


# ── Phoenix tracing (optional) ────────────────────────────────────────────────

def _setup_tracing() -> None:
    """
    Instruments all LLM calls with Arize Phoenix if PHOENIX_ENDPOINT is set.
    Completely silent / no-op if PHOENIX_ENDPOINT isn't set, or if the
    openinference packages aren't installed.
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

        instrumented: list[str] = []
        try:
            from openinference.instrumentation.groq import GroqInstrumentor
            GroqInstrumentor().instrument(tracer_provider=provider)
            instrumented.append("groq")
        except ImportError:
            pass

        # OpenAI instrumentation covers Sarvam-M (OpenAI-compatible client).
        try:
            from openinference.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=provider)
            instrumented.append("openai/sarvam")
        except ImportError:
            pass

        # Anthropic instrumentation — ready for when Claude is registered.
        try:
            from openinference.instrumentation.anthropic import AnthropicInstrumentor
            AnthropicInstrumentor().instrument(tracer_provider=provider)
            instrumented.append("anthropic")
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
                "Install: pip install openinference-instrumentation-groq "
                "openinference-instrumentation-openai"
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


# ── Provider protocol + registry (Phase 19) ───────────────────────────────────

class _InstructorClient(Protocol):
    """Minimal duck type — any instructor-patched client with chat.completions.create."""
    @property
    def chat(self) -> Any: ...


@dataclass
class Provider:
    """
    A registered LLM provider.

    Fields:
      name         — unique key, e.g. "groq" | "sarvam" | "anthropic"
      model        — default model id for this provider
      client_factory — lazy callable returning an instructor-patched client, or
                       None if the provider is not configured (missing API key).
                       Factory is cached on first successful call.
      supports_languages — tuple of language codes this provider is preferred for.
                           Empty tuple = fallback-only.
    """
    name:               str
    model:              str
    client_factory:     Callable[[], _InstructorClient | None]
    supports_languages: tuple[str, ...] = ()
    # Cached client — populated lazily by _get_client
    _client:            Any = field(default=None, repr=False)

    def get_client(self) -> _InstructorClient | None:
        if self._client is None:
            self._client = self.client_factory()
        return self._client


_PROVIDERS: dict[str, Provider] = {}


def register_provider(provider: Provider) -> None:
    """Register a provider. Safe to call multiple times — later calls replace."""
    _PROVIDERS[provider.name] = provider


def list_providers() -> list[str]:
    """Names of all registered providers (configured + not-yet-configured)."""
    return list(_PROVIDERS.keys())


# ── Built-in providers ────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _make_groq_client() -> _InstructorClient | None:
    if not GROQ_API_KEY:
        return None
    return instructor.from_groq(
        Groq(api_key=GROQ_API_KEY),
        mode=instructor.Mode.JSON,
    )


@functools.lru_cache(maxsize=1)
def _make_sarvam_client() -> _InstructorClient | None:
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


@functools.lru_cache(maxsize=1)
def _make_anthropic_client() -> _InstructorClient | None:
    """
    Anthropic Claude — frontier model for Sutradhar's English synthesis and
    Vidushak's adversarial critique. Reached via `model_hint="anthropic"`.

    We deliberately leave `supports_languages` empty: we do NOT want this
    provider picked automatically by language routing. Callers opt in with
    model_hint — so every other agent keeps Groq by default and the cost
    envelope stays predictable.

    Fails silently (returns None) if:
      - ANTHROPIC_API_KEY is unset (dev machine without key)
      - `anthropic` pip dep isn't installed
      - instructor.from_anthropic hits an import-time issue
    The router then ignores model_hint="anthropic" and falls through to
    language routing, so pipeline runs stay green.
    """
    if not ANTHROPIC_API_KEY:
        return None
    try:
        from anthropic import Anthropic
        return instructor.from_anthropic(
            Anthropic(api_key=ANTHROPIC_API_KEY),
            mode=instructor.Mode.ANTHROPIC_JSON,
        )
    except ImportError:
        emit_progress(
            "[llm] Anthropic key set but `anthropic` pip dep missing — "
            "run `pip install anthropic` to enable Opus routing."
        )
        return None
    except Exception as e:
        emit_progress(f"[llm] Anthropic client init failed: {e} — Opus routing disabled")
        return None


# Register built-ins at import time.
register_provider(Provider(
    name               = "groq",
    model              = GROQ_MODEL,
    client_factory     = _make_groq_client,
    supports_languages = ("en",),     # preferred for English; universal fallback
))
register_provider(Provider(
    name               = "sarvam",
    model              = SARVAM_MODEL,
    client_factory     = _make_sarvam_client,
    supports_languages = ("bn", "hi", "ta", "te", "ml", "kn", "gu", "mr"),  # Indic
))
register_provider(Provider(
    name               = "anthropic",
    model              = ANTHROPIC_MODEL,
    client_factory     = _make_anthropic_client,
    supports_languages = (),          # opt-in only — callers must pass model_hint="anthropic"
))


# ── Routing ───────────────────────────────────────────────────────────────────

def route(
    language:   str        = "en",
    model_hint: str | None = None,
) -> list[Provider]:
    """
    Return the ordered list of providers to try for this call.
    Callers iterate over this list; first successful response wins.

    Rules (in priority order):
      1. If model_hint is supplied and registered → return [that provider] only.
         (Hard override — no fallback. Caller asked for specific provider.)
      2. Otherwise: all providers supporting `language`, in registration order,
         followed by all other *configured* providers as fallback.
      3. Unconfigured providers (client_factory → None) are filtered out.

    Design notes:
      - Fallback lets Sarvam→Groq work out of the box.
      - Hard override lets eval harness pin a specific model for reproducibility.
      - Unknown language silently falls through to fallback (no exception).
    """
    if model_hint:
        p = _PROVIDERS.get(model_hint)
        if p and p.get_client() is not None:
            return [p]
        # Unknown / unconfigured hint → ignore hint, fall through to language routing
        emit_progress(f"[llm/router] model_hint='{model_hint}' not available — using language routing")

    primary:  list[Provider] = []
    fallback: list[Provider] = []
    for p in _PROVIDERS.values():
        if p.get_client() is None:
            continue
        if language in p.supports_languages:
            primary.append(p)
        else:
            fallback.append(p)

    return primary + fallback


# ── Main call function (public API — signature preserved) ─────────────────────

def call_llm(
    system:         str,
    user:           str,
    response_model: type[T],
    temperature:    float = 0.3,
    max_tokens:     int   = 4096,
    max_retries:    int   = 3,
    language:       str   = "en",
    model_hint:     str | None = None,   # Phase 19: optional hard override
) -> T:
    """
    Unified LLM call with router-based provider selection.

    Backwards-compatible: existing `call_llm(..., language="bn")` calls keep
    working. New `model_hint` arg is for eval harness / debugging — pin a
    specific provider regardless of language.

    On each provider attempt:
      1. Sends system + user messages with JSON mode.
      2. instructor extracts JSON and validates against response_model.
      3. If validation fails, instructor retries up to max_retries.
      4. On any exception, the NEXT provider in the router chain is tried.
      5. Final failure raises the last provider's exception.
    """
    _ensure_tracing()

    chain = route(language=language, model_hint=model_hint)
    if not chain:
        raise RuntimeError(
            "No LLM provider available. Set GROQ_API_KEY (required) or "
            "SARVAM_API_KEY (Bengali content). Check `llm.list_providers()`."
        )

    last_error: Exception | None = None
    for idx, provider in enumerate(chain):
        client = provider.get_client()
        if client is None:
            continue
        try:
            return client.chat.completions.create(
                model          = provider.model,
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
            last_error = e
            # Only log fallback noise if there's actually a next provider to try.
            if idx + 1 < len(chain):
                next_name = chain[idx + 1].name
                emit_progress(
                    f"[llm/{provider.name}] failed ({type(e).__name__}: {str(e)[:80]}) "
                    f"— falling back to {next_name}"
                )

    # Exhausted the chain
    assert last_error is not None
    raise last_error


__all__ = ["call_llm", "route", "Provider", "register_provider", "list_providers"]
