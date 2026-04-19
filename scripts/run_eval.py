"""
scripts/run_eval.py
====================
Phase 18 — Pipeline Eval Harness.

Pulls a sample of MCQs that have already been approved + promoted to
`pyq_bank_v2`, reconstructs them into MCQItem objects, and runs বিদূষক's
verifier against them. Reports:

  - total sampled
  - bidushak_clean      — MCQs that pass the verifier with zero issues
  - bidushak_flagged    — MCQs the verifier would flag today
  - issue_breakdown     — which of the 7 checks fire most
  - stratified by (board, class_num, subject)

Why this matters
────────────────
Gyan AI's quality model is built around Vidushak catching errors before
they reach the bank. This harness answers: "If we re-ran Vidushak against
our live bank today, how many would it now catch?" — a direct measure of
verifier drift and a prerequisite for Phase 9 (DSPy optimisation — MIPROv2
needs a labelled dev set).

Usage:
    python -m scripts.run_eval --limit 50
    python -m scripts.run_eval --limit 100 --board WBBSE --json > eval.json

Exit codes:
    0  — eval completed (regardless of pass rate)
    1  — fatal error before any MCQ was scored
    2  — Supabase connection / env misconfig
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from dataclasses import dataclass, asdict, field

from supabase import create_client

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from models.schemas import MCQItem, MCQOption, TaxonomySlice, Segment
from agents import vidushak


@dataclass
class EvalRow:
    mcq_id:    str | None
    label:     str
    ok:        bool
    issues:    list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    sampled:          int = 0
    clean:            int = 0
    flagged:          int = 0
    parse_failures:   int = 0
    issue_breakdown:  dict = field(default_factory=dict)
    by_board:         dict = field(default_factory=dict)
    rows:             list[EvalRow] = field(default_factory=list)

    @property
    def clean_rate(self) -> float:
        denom = self.sampled - self.parse_failures
        return (self.clean / denom) if denom else 0.0

    def to_dict(self) -> dict:
        return {
            "sampled":         self.sampled,
            "clean":           self.clean,
            "flagged":         self.flagged,
            "parse_failures":  self.parse_failures,
            "clean_rate":      round(self.clean_rate, 3),
            "issue_breakdown": self.issue_breakdown,
            "by_board":        self.by_board,
            "rows":            [asdict(r) for r in self.rows],
        }


# ── Row parsing ───────────────────────────────────────────────────────────────

def _row_to_mcq(row: dict) -> tuple[MCQItem | None, TaxonomySlice | None, str]:
    """
    pyq_bank_v2 rows use `question_payload` JSON. Different generations have
    stored it with slight schema drift — we try the main shape and fall back
    gracefully.
    """
    payload = row.get("question_payload") or {}
    mcq_id  = str(row.get("id") or payload.get("id") or "?")

    try:
        # Options can be dict {A:..., B:..., C:..., D:...} OR list[4]
        opts_raw = payload.get("options") or {}
        if isinstance(opts_raw, list) and len(opts_raw) == 4:
            options = MCQOption(A=opts_raw[0], B=opts_raw[1], C=opts_raw[2], D=opts_raw[3])
        elif isinstance(opts_raw, dict):
            options = MCQOption(
                A=str(opts_raw.get("A", "")),
                B=str(opts_raw.get("B", "")),
                C=str(opts_raw.get("C", "")),
                D=str(opts_raw.get("D", "")),
            )
        else:
            return None, None, mcq_id

        mcq = MCQItem(
            question          = str(payload.get("question", "")).strip(),
            options           = options,
            correct           = str(payload.get("correct") or payload.get("answer") or "A").strip()[:1].upper(),
            reasoning_process = str(payload.get("reasoning_process") or payload.get("reasoning") or "n/a"),
            explanation       = str(payload.get("explanation") or payload.get("reasoning") or "n/a"),
            difficulty        = str(payload.get("difficulty", "medium")),
            bloom_level       = str(payload.get("bloom_level", "understand")),
            topic_tag         = str(payload.get("topic_tag") or payload.get("topic") or "general"),
        )

        tax = TaxonomySlice(
            segment   = Segment(payload.get("segment", "school")),
            board     = payload.get("board"),
            class_num = payload.get("class_num"),
            subject   = payload.get("subject"),
            count     = 1,
        )
        return mcq, tax, mcq_id
    except Exception:
        return None, None, mcq_id


# ── Eval loop ─────────────────────────────────────────────────────────────────

def _fetch_sample(limit: int, board: str | None) -> list[dict]:
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    q = db.table("pyq_bank_v2").select("id, question_payload")
    # Pull a larger pool then sample — avoids bias toward recent inserts
    rows = q.limit(max(limit * 4, 200)).execute().data or []
    if board:
        rows = [r for r in rows if (r.get("question_payload") or {}).get("board") == board]
    random.shuffle(rows)
    return rows[:limit]


def run_eval(limit: int = 50, board: str | None = None) -> EvalReport:
    report = EvalReport()
    rows = _fetch_sample(limit, board)
    report.sampled = len(rows)

    if not rows:
        return report

    issue_counter: Counter = Counter()
    board_counter: dict[str, dict] = {}

    for row in rows:
        mcq, taxonomy, mcq_id = _row_to_mcq(row)
        if not mcq or not taxonomy:
            report.parse_failures += 1
            continue

        label = f"{taxonomy.board} · Class {taxonomy.class_num} · {taxonomy.subject}"
        bkey  = taxonomy.board or "unknown"
        board_counter.setdefault(bkey, {"total": 0, "clean": 0, "flagged": 0})
        board_counter[bkey]["total"] += 1

        try:
            _, audit = vidushak.verify_and_repair([mcq], taxonomy, taxonomy.label or label)
            issues = [s for s in audit.get("issue_samples", []) if s]
            if audit.get("issues_found", 0) == 0:
                report.clean += 1
                board_counter[bkey]["clean"] += 1
                report.rows.append(EvalRow(mcq_id=mcq_id, label=label, ok=True))
            else:
                report.flagged += 1
                board_counter[bkey]["flagged"] += 1
                # Tag each issue into buckets (first uppercase token before ":")
                for s in issues:
                    head = s.split(":", 1)[0].strip()[:40]
                    issue_counter[head] += 1
                report.rows.append(EvalRow(
                    mcq_id=mcq_id, label=label, ok=False, issues=issues[:3],
                ))
        except Exception as e:
            report.parse_failures += 1
            report.rows.append(EvalRow(
                mcq_id=mcq_id, label=label, ok=False,
                issues=[f"verifier_error: {type(e).__name__}: {e}"[:200]],
            ))

    report.issue_breakdown = dict(issue_counter.most_common())
    report.by_board        = board_counter
    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Run Phase 18 eval harness (Vidushak vs live bank).")
    ap.add_argument("--limit", type=int, default=50, help="Max MCQs to sample.")
    ap.add_argument("--board", default=None, help="Restrict to one board (e.g. WBBSE).")
    ap.add_argument("--json",  action="store_true", help="Emit full EvalReport as JSON.")
    args = ap.parse_args()

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("fatal: SUPABASE_URL / SUPABASE_SERVICE_KEY not set", file=sys.stderr)
        return 2

    try:
        report = run_eval(limit=args.limit, board=args.board)
    except Exception as e:
        print(f"fatal: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0

    # Human-readable summary
    print()
    print(f"— বিদূষক Eval Report —")
    print(f"  sampled         : {report.sampled}")
    print(f"  clean           : {report.clean}")
    print(f"  flagged         : {report.flagged}")
    print(f"  parse_failures  : {report.parse_failures}")
    print(f"  clean_rate      : {report.clean_rate:.1%}")
    print()
    if report.issue_breakdown:
        print("  Issue breakdown:")
        for issue, n in list(report.issue_breakdown.items())[:10]:
            print(f"    {n:>4}  {issue}")
        print()
    if report.by_board:
        print("  By board:")
        for b, stats in report.by_board.items():
            t = stats["total"] or 1
            print(f"    {b:<10}  {stats['clean']}/{t} clean  ({stats['clean']/t:.0%})")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
