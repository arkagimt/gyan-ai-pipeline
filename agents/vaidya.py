"""
বৈদ্য — The Pipeline Physician
================================
Bengali:  বৈদ্য
Website:  gyanagent.in/about  →  "The Pipeline Physician" (Phase 16 — planned)

Role:   Stateless health-check agent. Pings every external dependency the
        pipeline relies on, and reports recent success rates from the
        triage queue. Designed to run on a cron (daily) or on-demand
        from the admin UI.

No LLM for the health checks themselves — but Vaidya does make one tiny
Groq completion to verify the model endpoint is alive end-to-end. Cost: <1¢/day.

Checks (HealthReport):
  1. groq            — 2-token completion against GROQ_MODEL
  2. groq_guard      — llama-guard-3-8b reachable
  3. sarvam          — skipped if SARVAM_API_KEY unset (Bengali routing is optional)
  4. supabase        — SELECT count(*) on core tables
  5. triage_rate     — (approved / total) over the last 24h from triage queue
  6. recent_failures — rejected count in last 24h + last rejection_reason

Exit codes (CLI):
  0 — all green
  1 — any check failed
  2 — env-var misconfiguration (can't even try)

Why Vaidya and not Sanjaya? Sanjaya is a passive chronicler — he watches
and logs. Vaidya is active — he pokes the patient and reports symptoms.
Separation of concerns: observer vs physician.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

from config import (
    GROQ_API_KEY, GROQ_MODEL, GROQ_GUARD_MODEL,
    SARVAM_API_KEY, SARVAM_MODEL,
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    emit_agent, emit_progress,
)


# ── Check result ──────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name:       str
    ok:         bool
    latency_ms: float | None = None
    detail:     str = ""
    skipped:    bool = False


@dataclass
class HealthReport:
    checks:       list[CheckResult] = field(default_factory=list)
    started_at:   str = ""
    ended_at:     str = ""

    @property
    def all_ok(self) -> bool:
        return all(c.ok or c.skipped for c in self.checks)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.ok and not c.skipped)

    def to_dict(self) -> dict:
        return {
            "started_at":  self.started_at,
            "ended_at":    self.ended_at,
            "all_ok":      self.all_ok,
            "fail_count":  self.fail_count,
            "checks":      [asdict(c) for c in self.checks],
        }


# ── Individual checks ─────────────────────────────────────────────────────────

def _time(fn):
    """Returns (result, latency_ms)."""
    t0 = time.perf_counter()
    out = fn()
    return out, round((time.perf_counter() - t0) * 1000, 1)


def _check_groq(model: str, name: str) -> CheckResult:
    if not GROQ_API_KEY:
        return CheckResult(name=name, ok=False, detail="GROQ_API_KEY not set")
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        def _call():
            return client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
                temperature=0,
            )
        resp, ms = _time(_call)
        return CheckResult(
            name=name, ok=True, latency_ms=ms,
            detail=f"model={model} tokens_in={resp.usage.prompt_tokens if resp.usage else '?'}",
        )
    except Exception as e:
        return CheckResult(name=name, ok=False, detail=f"{type(e).__name__}: {e}"[:200])


def _check_sarvam() -> CheckResult:
    if not SARVAM_API_KEY:
        return CheckResult(name="sarvam", ok=True, skipped=True,
                           detail="SARVAM_API_KEY not set — Bengali routing disabled")
    try:
        from openai import OpenAI
        from config import SARVAM_BASE_URL
        client = OpenAI(api_key=SARVAM_API_KEY, base_url=SARVAM_BASE_URL)
        def _call():
            return client.chat.completions.create(
                model=SARVAM_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
                temperature=0,
            )
        _, ms = _time(_call)
        return CheckResult(name="sarvam", ok=True, latency_ms=ms,
                           detail=f"model={SARVAM_MODEL}")
    except Exception as e:
        return CheckResult(name="sarvam", ok=False,
                           detail=f"{type(e).__name__}: {e}"[:200])


def _check_supabase() -> tuple[CheckResult, dict | None]:
    """Also returns the counts dict for reuse by triage_rate check."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return (CheckResult(name="supabase", ok=False,
                            detail="SUPABASE_URL or SUPABASE_SERVICE_KEY missing"), None)
    try:
        from supabase import create_client
        db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        def _counts():
            out = {}
            for table in ("pyq_bank_v2", "study_materials", "ingestion_triage_queue"):
                try:
                    out[table] = db.table(table).select("*", count="exact", head=True).execute().count or 0
                except Exception as e:
                    out[table] = f"err: {e}"[:80]
            return out

        counts, ms = _time(_counts)
        bad = [t for t, v in counts.items() if isinstance(v, str)]
        if bad:
            return (CheckResult(name="supabase", ok=False, latency_ms=ms,
                                detail=f"tables failed: {bad} · counts={counts}"), counts)
        return (CheckResult(name="supabase", ok=True, latency_ms=ms,
                            detail=" · ".join(f"{k}={v}" for k, v in counts.items())), counts)
    except Exception as e:
        return (CheckResult(name="supabase", ok=False,
                            detail=f"{type(e).__name__}: {e}"[:200]), None)


def _check_triage_rate() -> CheckResult:
    """Approval ratio over the last 24h — early warning for pipeline regression."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return CheckResult(name="triage_rate", ok=False, skipped=True,
                           detail="Supabase not configured")
    try:
        from supabase import create_client
        db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        def _fetch():
            return (
                db.table("ingestion_triage_queue")
                .select("status, rejection_reason, reviewed_at")
                .gte("reviewed_at", since)
                .execute()
            ).data or []

        rows, ms = _time(_fetch)
        if not rows:
            return CheckResult(name="triage_rate", ok=True, skipped=True, latency_ms=ms,
                               detail="no items reviewed in last 24h")

        approved = sum(1 for r in rows if r.get("status") == "approved")
        rejected = sum(1 for r in rows if r.get("status") == "rejected")
        total    = approved + rejected
        rate     = (approved / total) if total else 1.0

        # Alert if < 50% approval over a meaningful sample
        ok = total < 5 or rate >= 0.5
        last_reject = next(
            (r.get("rejection_reason") for r in rows if r.get("status") == "rejected" and r.get("rejection_reason")),
            None,
        )

        detail = f"24h · approved={approved}/{total} ({rate:.0%})"
        if last_reject:
            detail += f" · last_reject='{str(last_reject)[:80]}'"
        return CheckResult(name="triage_rate", ok=ok, latency_ms=ms, detail=detail)

    except Exception as e:
        return CheckResult(name="triage_rate", ok=False,
                           detail=f"{type(e).__name__}: {e}"[:200])


# ── Main API ──────────────────────────────────────────────────────────────────

def run_healthcheck() -> HealthReport:
    """
    Runs all checks sequentially. Returns a HealthReport.
    Safe to call on any schedule — no side effects.
    """
    emit_agent("বৈদ্য", "Running pipeline health check...")
    report = HealthReport(started_at=datetime.now(timezone.utc).isoformat())

    report.checks.append(_check_groq(GROQ_MODEL, "groq"))
    report.checks.append(_check_groq(GROQ_GUARD_MODEL, "groq_guard"))
    report.checks.append(_check_sarvam())

    sb_check, _counts = _check_supabase()
    report.checks.append(sb_check)

    report.checks.append(_check_triage_rate())

    report.ended_at = datetime.now(timezone.utc).isoformat()

    for c in report.checks:
        status = "✓" if c.ok else ("⊘ skipped" if c.skipped else "✗")
        emit_progress(f"[বৈদ্য] {status} {c.name} — {c.detail}")

    emit_agent(
        "বৈদ্য",
        f"Health check complete — fail_count={report.fail_count}, all_ok={report.all_ok}",
    )
    return report


__all__ = ["run_healthcheck", "HealthReport", "CheckResult"]
