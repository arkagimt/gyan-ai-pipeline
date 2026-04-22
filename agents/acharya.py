"""
আচার্য — The Curriculum Orchestrator
=====================================
Bengali:  আচার্য
Website:  gyanagent.in/about  →  "The Curriculum Orchestrator"
          "গণকের প্রাধান্য-তালিকা ধরে আমি নিজেই পাইপলাইন চালাই।
           মানুষ বিশ্রাম নেবে, চাকা ঘুরতে থাকবে।"
          (I take গণক's priority list and run the pipeline myself.
           Humans rest — the wheel keeps turning.)

Role:   Autonomous batch orchestrator. Reads গণক's TopicPriority list,
        dispatches GitHub Actions ingest workflows for the top-N slots,
        and returns a dispatch receipt.

No LLM. Pure glue between গণক (analyst) and the ingest workflows.

─────────────────────────────────────────────────────────────────────────────
Design notes:

1. Acharya is stateless. It does NOT wait for workflow completion —
   it fires `workflow_dispatch` and moves on. GitHub Actions handles
   execution; সঞ্জয় sees the new rows land in triage and raises milestones.

2. Rate-limit baked in (`delay_s` between dispatches) so we don't flood
   the Groq API or hit GitHub's "20 concurrent workflow runs per repo" cap.

3. Segment routing:
     school                        → ingest_school.yml
     entrance / recruitment /
        competitive (legacy alias) → ingest_competitive.yml
     it                            → ingest_it.yml

4. dry_run=True returns the would-be dispatch list without hitting the API.
   The admin UI uses this for a preview before the real run.

5. Env: reads GITHUB_PAT + GITHUB_REPO. Also supports being called from
   Streamlit where secrets come through `st.secrets` — pass explicit
   `pat`/`repo` kwargs in that case.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict, field
from typing import Iterable

import requests

from agents import ganak
from agents.ganak import TopicPriority
from config import emit_agent, emit_progress


# ── Constants ─────────────────────────────────────────────────────────────────

_WORKFLOW_BY_SEGMENT = {
    "school":      "ingest_school.yml",
    # Entrance + Recruitment both route to ingest_competitive.yml for now —
    # the workflow is taxonomy-driven (authority/exam/topic inputs), so the
    # pipeline run self-classifies via derive_scope_nature + nature tagging
    # in supabase_loader. Split workflows only if the yml args diverge.
    "entrance":    "ingest_competitive.yml",
    "recruitment": "ingest_competitive.yml",
    "competitive": "ingest_competitive.yml",   # legacy alias
    "it":          "ingest_it.yml",
}

# GitHub caps concurrent workflow runs per repo. Stay well under it so we
# leave headroom for manual admin dispatches.
_DEFAULT_BATCH_LIMIT  = 5
_DEFAULT_DELAY_S      = 3.0   # between dispatches — API etiquette, not throughput
_DEFAULT_PER_RUN_MCQS = 10    # matches TopicPriority.taxonomy_slice() cap


# ── Receipt model ─────────────────────────────────────────────────────────────

@dataclass
class DispatchResult:
    """One priority → one workflow dispatch attempt."""
    priority:    TopicPriority
    workflow:    str
    inputs:      dict
    status_code: int | None = None    # None = dry_run or error-before-send
    ok:          bool        = False
    message:     str         = ""

    def to_dict(self) -> dict:
        return {
            "segment":    self.priority.segment,
            "label":      _priority_label(self.priority),
            "priority":   self.priority.priority_score,
            "gap":        self.priority.gap,
            "workflow":   self.workflow,
            "inputs":     self.inputs,
            "ok":         self.ok,
            "status_code": self.status_code,
            "message":    self.message,
        }


@dataclass
class BatchReceipt:
    """Summary of one run_batch() call — ships to UI + logs."""
    dispatched:  int = 0
    failed:      int = 0
    skipped:     int = 0
    dry_run:     bool = False
    results:     list[DispatchResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dispatched": self.dispatched,
            "failed":     self.failed,
            "skipped":    self.skipped,
            "dry_run":    self.dry_run,
            "results":    [r.to_dict() for r in self.results],
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

_COMPETITIVE_SEGMENTS = ("competitive", "entrance", "recruitment")


def _priority_label(p: TopicPriority) -> str:
    if p.segment == "school":
        return f"{p.board} · Class {p.class_num} · {p.subject}"
    if p.segment in _COMPETITIVE_SEGMENTS:
        return f"{p.authority} · {p.exam} · {p.topic}"
    return f"{p.provider} · {p.exam} · {p.topic}"


def _priority_to_inputs(p: TopicPriority, per_run_mcqs: int) -> dict:
    """Map a TopicPriority → workflow_dispatch inputs (all strings — GH requires)."""
    count = str(min(p.gap, per_run_mcqs))

    if p.segment == "school":
        return {
            "board":     p.board or "",
            "class_num": str(p.class_num) if p.class_num is not None else "",
            "subject":   p.subject or "",
            "count":     count,
        }
    if p.segment in _COMPETITIVE_SEGMENTS:
        # Pass `segment` through so ingest_competitive.yml forwards it to
        # gyan_pipeline.py — this is what lets JEE-entrance get tagged
        # nature=entrance instead of the legacy-alias "competitive" →
        # nature=recruitment default in derive_scope_nature.
        return {
            "segment":   p.segment,
            "authority": p.authority or "",
            "exam":      p.exam or "",
            "topic":     p.topic or "",
            "count":     count,
        }
    # IT
    return {
        "provider": p.provider or "",
        "exam":     p.exam or "",
        "topic":    p.topic or "",
        "count":    count,
    }


def _dispatch(
    workflow: str,
    inputs:   dict,
    pat:      str,
    repo:     str,
    ref:      str = "main",
    timeout:  float = 15.0,
) -> tuple[int, str]:
    """
    Fire workflow_dispatch. Returns (status_code, message).
    204 = success. Anything else = failure — caller inspects.
    """
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    resp = requests.post(
        url,
        headers={
            "Authorization":        f"Bearer {pat}",
            "Accept":               "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": ref, "inputs": {k: v for k, v in inputs.items() if v}},
        timeout=timeout,
    )
    if resp.status_code == 204:
        return 204, "dispatched"
    return resp.status_code, resp.text[:300]


# ── Main API ──────────────────────────────────────────────────────────────────

def run_batch(
    *,
    coverage:       dict,
    limit:          int = _DEFAULT_BATCH_LIMIT,
    segment_filter: str | None = "school",
    board_filter:   str | None = None,
    class_filter:   int | None = None,
    per_run_mcqs:   int = _DEFAULT_PER_RUN_MCQS,
    delay_s:        float = _DEFAULT_DELAY_S,
    dry_run:        bool = False,
    pat:            str | None = None,
    repo:           str | None = None,
    ref:            str = "main",
    priorities:     Iterable[TopicPriority] | None = None,
) -> BatchReceipt:
    """
    আচার্য's main entry point.

    Args:
        coverage:        {(board, class_num, subject): count} — usually from
                         fetch_coverage(). Ignored if `priorities` is supplied.
        limit:           how many workflows to dispatch this batch.
        segment_filter:  "school" | "entrance" | "recruitment" | "competitive"
                         (legacy alias — pulls entrance+recruitment) | "it" | None.
        board_filter:    optional board restriction (e.g. "WBBSE").
        class_filter:    optional class restriction (e.g. 10).
        per_run_mcqs:    MCQs requested per dispatched run.
        delay_s:         sleep between dispatches — respects GH + Groq limits.
        dry_run:         if True, return the planned dispatch list without
                         calling GitHub. Admin UI uses this for preview.
        pat / repo:      GitHub PAT + "owner/repo". Fall back to env vars if
                         not supplied. Streamlit passes them from st.secrets.
        ref:             branch to run workflows on. Default "main".
        priorities:      pre-computed TopicPriority list. When supplied,
                         Acharya skips the গণক call and uses these directly —
                         useful when the admin has hand-picked slots.

    Returns a BatchReceipt summarising every dispatch attempt.
    """
    emit_agent("আচার্য", f"Starting batch — limit={limit}, segment={segment_filter}, dry_run={dry_run}")

    receipt = BatchReceipt(dry_run=dry_run)

    # ── 1. Get priorities (either passed in, or ask গণক) ──────────────────────
    if priorities is None:
        priorities = ganak.analyze(
            coverage       = coverage,
            segment_filter = segment_filter,
            board_filter   = board_filter,
            class_filter   = class_filter,
            top_n          = limit,
        )
    priorities = list(priorities)[:limit]

    if not priorities:
        emit_progress("[আচার্য] No priorities to dispatch — curriculum already covered?")
        return receipt

    # ── 2. Resolve credentials (skip for dry_run) ─────────────────────────────
    if not dry_run:
        pat  = pat  or os.environ.get("GITHUB_PAT", "")
        repo = repo or os.environ.get("GITHUB_REPO", "")
        if not pat or not repo:
            raise RuntimeError(
                "আচার্য needs GITHUB_PAT + GITHUB_REPO (env vars or kwargs). "
                "Set them in .env or pass explicitly from Streamlit secrets."
            )

    # ── 3. Walk the list, dispatch, record ────────────────────────────────────
    for idx, p in enumerate(priorities, 1):
        workflow = _WORKFLOW_BY_SEGMENT.get(p.segment)
        if not workflow:
            receipt.results.append(DispatchResult(
                priority=p, workflow="(unknown)", inputs={},
                ok=False, message=f"No workflow mapped for segment={p.segment}",
            ))
            receipt.skipped += 1
            continue

        inputs = _priority_to_inputs(p, per_run_mcqs=per_run_mcqs)

        if dry_run:
            receipt.results.append(DispatchResult(
                priority=p, workflow=workflow, inputs=inputs,
                ok=True, message="dry_run — not dispatched",
            ))
            receipt.dispatched += 1
            continue

        try:
            status, msg = _dispatch(workflow, inputs, pat=pat, repo=repo, ref=ref)
            ok = (status == 204)
            receipt.results.append(DispatchResult(
                priority=p, workflow=workflow, inputs=inputs,
                status_code=status, ok=ok, message=msg,
            ))
            if ok:
                receipt.dispatched += 1
                emit_progress(f"[আচার্য] ({idx}/{len(priorities)}) ✓ {_priority_label(p)} → {workflow}")
            else:
                receipt.failed += 1
                emit_progress(f"[আচার্য] ({idx}/{len(priorities)}) ✗ {_priority_label(p)} → {status} {msg}")
        except Exception as e:
            receipt.failed += 1
            receipt.results.append(DispatchResult(
                priority=p, workflow=workflow, inputs=inputs,
                ok=False, message=f"exception: {e}",
            ))
            emit_progress(f"[আচার্য] ({idx}/{len(priorities)}) ✗ exception: {e}")

        # Rate-limit between dispatches (skip after the last one)
        if idx < len(priorities) and delay_s > 0:
            time.sleep(delay_s)

    emit_agent(
        "আচার্য",
        f"Batch complete — dispatched={receipt.dispatched}, "
        f"failed={receipt.failed}, skipped={receipt.skipped}"
        + (" (dry-run)" if dry_run else ""),
    )
    return receipt


__all__ = ["run_batch", "BatchReceipt", "DispatchResult"]
