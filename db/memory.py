"""
সঞ্জয় — The Omniscient Chronicler
====================================
Bengali:  সঞ্জয় (sañjaya — "the one who sees all")
Website:  gyanagent.in/about → Sanjaya
Role:     Passive observer over the whole pipeline — owns (1) dedup memory
          lookups across ingestion_triage_queue + pyq_bank_v2, and
          (2) milestone tracking that fires DSPy/pgvector/PydanticAI triggers.
Scope:    No LLM. Pure Supabase reads + threshold arithmetic.

Note on file location:
  Historically this lived at `db/memory.py` because Sanjaya's first job was
  dedup memory. Per AGENTS.md rule #1 (file name = agent_id) this file will
  move to `agents/sanjaya.py` after Phase 6 — kept here for now to avoid
  churning every import site mid-stream.

Before generating new content, the pipeline checks whether MCQs for this
exact taxonomy slice already exist in Supabase. This prevents:

  • Duplicate entries in ingestion_triage_queue (wasted admin review time)
  • Wasted LLM API tokens on already-covered topics
  • Students seeing repeated questions with slightly different wording

Two-pronged check:
  1. ingestion_triage_queue (status ≠ rejected)
       → pending items waiting for human review
       → approved items already promoted but count as "done"
  2. pyq_bank_v2
       → fully live content served to students

The pipeline respects the requested count:
  ┌─────────────────────────────────────────────────────────────────┐
  │  existing ≥ requested  →  SKIP entirely (0 tokens spent)       │
  │  0 < existing < requested  →  TOP-UP (generate the difference) │
  │  existing == 0  →  proceed normally (full count)               │
  └─────────────────────────────────────────────────────────────────┘

Milestone tracking (Sanjaya):
  After every pipeline run, the total MCQ count is checked against
  known milestones. See SANJAYA_CHRONICLES.md for the DSPy trigger.
"""

from __future__ import annotations
import requests

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, emit_progress
from models.schemas import TaxonomySlice


REST_URL = f"{SUPABASE_URL}/rest/v1"
_HEADERS = {
    "apikey":        SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type":  "application/json",
    # Prefer: count=exact tells PostgREST to return total in Content-Range header
    "Prefer":        "count=exact",
}


# ── Sanjaya Milestone Registry ────────────────────────────────────────────────
# Add new milestones here. Format: (threshold, message)
# Sanjaya will emit a starred progress line when any threshold is crossed.
MILESTONES: list[tuple[int, str]] = [
    (100,  "🎯 100 live MCQs! Pilot cohort ready. Start tracking first student completions."),
    (250,  "📈 250 MCQs! Enough for one full exam mock test per subject."),
    (500,  "🚀 [SANJAYA MILESTONE] 500 MCQs reached!\n"
           "    ACTION REQUIRED: Implement DSPy optimizer to auto-tune agent prompts.\n"
           "    See SANJAYA_CHRONICLES.md → Entry SC-001 for implementation plan.\n"
           "    DSPy repo: github.com/stanfordnlp/dspy (MIT License)"),
    (1000, "🏆 1000 MCQs! Consider enabling pgvector semantic search for অন্বেষক."),
    (2500, "⚡ 2500 MCQs! PydanticAI agents (বেতাল, নারদ) now have enough training data."),
    (5000, "🌟 5000 MCQs! Full WB curriculum coverage approaching. Evaluate fine-tuning."),
]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _count_in_triage(label: str) -> int:
    """
    Count MCQs in ingestion_triage_queue for this taxonomy label.
    Excludes rejected items — they failed QA, so we *should* regenerate those.
    """
    try:
        resp = requests.get(
            f"{REST_URL}/ingestion_triage_queue",
            headers=_HEADERS,
            params={
                "payload_type":              "eq.pyq",
                "raw_data->>taxonomy_label": f"eq.{label}",
                "status":                    "not.eq.rejected",
                "select":                    "id",
                "limit":                     "0",   # no rows, just count
            },
            timeout=10,
        )
        if resp.status_code in (200, 206):
            # Content-Range: */N  (when limit=0, PostgREST uses */N format)
            content_range = resp.headers.get("Content-Range", "*/0")
            total = content_range.split("/")[-1]
            return int(total) if total.isdigit() else 0
        emit_progress(f"[memory] Triage count HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as exc:
        emit_progress(f"[memory] Triage count error (non-blocking): {exc}")
    return 0


def _count_in_pyq_bank(label: str) -> int:
    """
    Count MCQs already promoted to pyq_bank_v2 for this taxonomy label.
    question_payload is the full raw_data dict — taxonomy_label lives inside it.
    """
    try:
        resp = requests.get(
            f"{REST_URL}/pyq_bank_v2",
            headers=_HEADERS,
            params={
                "question_payload->>taxonomy_label": f"eq.{label}",
                "select":                            "id",
                "limit":                             "0",
            },
            timeout=10,
        )
        if resp.status_code in (200, 206):
            content_range = resp.headers.get("Content-Range", "*/0")
            total = content_range.split("/")[-1]
            return int(total) if total.isdigit() else 0
        # 404 here just means no approved content yet — totally normal
        if resp.status_code != 404:
            emit_progress(f"[memory] pyq_bank count HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as exc:
        emit_progress(f"[memory] pyq_bank count error (non-blocking): {exc}")
    return 0


def _total_live_mcqs() -> int:
    """Returns total MCQ count across all taxonomies in pyq_bank_v2."""
    try:
        resp = requests.get(
            f"{REST_URL}/pyq_bank_v2",
            headers=_HEADERS,
            params={"select": "id", "limit": "0"},
            timeout=10,
        )
        if resp.status_code in (200, 206):
            content_range = resp.headers.get("Content-Range", "*/0")
            total = content_range.split("/")[-1]
            return int(total) if total.isdigit() else 0
    except Exception:
        pass
    return 0


# ── Milestone checker ─────────────────────────────────────────────────────────

def check_milestones(total: int) -> None:
    """
    Emit Sanjaya milestone alerts when total live MCQ count crosses thresholds.
    Called by gyan_pipeline.py after each successful Supabase push.
    """
    for threshold, message in MILESTONES:
        # Fire exactly once — when total has just crossed the threshold
        # (i.e., total >= threshold but total - newly_added might be < threshold)
        # We use a window of ±20 to avoid missing it if pipeline adds multiple MCQs
        if threshold <= total < threshold + 20:
            emit_progress(f"\n{'━'*60}")
            emit_progress(f"[SANJAYA] {message}")
            emit_progress(f"{'━'*60}\n")


# ── Public API ────────────────────────────────────────────────────────────────

def check_existing_mcqs(taxonomy: TaxonomySlice) -> int:
    """
    Returns total MCQ count already existing for this exact taxonomy slice
    across ingestion_triage_queue (non-rejected) and pyq_bank_v2.

    Called at the start of gyan_pipeline.run() to decide whether to:
      - Skip entirely (existing >= requested)
      - Top-up (generate only the missing count)
      - Proceed normally (no existing content)

    Always non-blocking: any Supabase error returns 0 (safe fallback — the
    pipeline will just generate as normal, duplicates go to triage for human review).
    """
    label        = taxonomy.label
    triage_count = _count_in_triage(label)
    bank_count   = _count_in_pyq_bank(label)
    total        = triage_count + bank_count

    if total > 0:
        emit_progress(
            f"[memory] «{label}»: "
            f"{bank_count} live + {triage_count} in triage = {total} existing MCQs"
        )

    return total


def after_push_checks(newly_added: int) -> None:
    """
    Run post-push housekeeping after a successful Supabase push:
      1. Fetch total live MCQ count
      2. Fire Sanjaya milestone alerts if thresholds crossed

    Called by gyan_pipeline.py with the count of MCQs just pushed.
    """
    if newly_added == 0:
        return

    total = _total_live_mcqs()
    if total > 0:
        emit_progress(f"[memory] Total live MCQs now: {total}")
        check_milestones(total)
