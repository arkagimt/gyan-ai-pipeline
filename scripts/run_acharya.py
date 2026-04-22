"""
scripts/run_acharya.py
======================
Thin CLI wrapper around agents.acharya.run_batch().

Examples:
    # Preview top-5 school priorities, don't dispatch
    python -m scripts.run_acharya --limit 5 --dry-run

    # Autonomous cron: fire top-3 WBBSE Class 10 workflows, 5s between
    python -m scripts.run_acharya --limit 3 --board WBBSE --class 10 --delay 5

    # Multi-segment sweep
    python -m scripts.run_acharya --limit 10 --segment competitive

Requires GITHUB_PAT + GITHUB_REPO in env (or .env) for non-dry-run mode.
Exit codes:
    0 — dispatched at least one workflow (or dry_run printed)
    1 — all dispatches failed
    2 — no priorities found (curriculum covered)
"""

from __future__ import annotations

import argparse
import json
import sys

from supabase import create_client

from agents import acharya
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY


def _bump_coverage(coverage: dict, payload: dict) -> None:
    """
    Extract a taxonomy key from a payload and increment its count.
    Keys match what ganak.analyze() looks up per segment:
      school      → (board, class_num, subject)
      entrance    → (authority, exam, topic)
      recruitment → (authority, exam, topic)
      it          → (provider, exam, topic)
    Silently skips rows that lack the required fields — legacy data is fine.
    """
    segment = str(payload.get("segment") or "").strip().lower()

    # School (default when segment missing but board+class present — back-compat
    # with legacy rows written before the segment column existed).
    if segment == "school" or (not segment and payload.get("board")):
        board   = str(payload.get("board") or "").strip()
        cls     = payload.get("class_num")
        subject = str(payload.get("subject") or "").strip()
        if board and cls is not None and subject:
            key = (board, int(cls), subject)
            coverage[key] = coverage.get(key, 0) + 1
        return

    if segment in ("entrance", "recruitment", "competitive"):
        authority = str(payload.get("authority") or "").strip()
        exam      = str(payload.get("exam") or "").strip()
        topic     = str(payload.get("topic") or "").strip()
        if authority and exam and topic:
            key = (authority, exam, topic)
            coverage[key] = coverage.get(key, 0) + 1
        return

    if segment == "it":
        provider = str(payload.get("provider") or "").strip()
        exam     = str(payload.get("exam") or "").strip()
        topic    = str(payload.get("topic") or "").strip()
        if provider and exam and topic:
            key = (provider, exam, topic)
            coverage[key] = coverage.get(key, 0) + 1
        return


def _fetch_coverage() -> dict:
    """
    Headless version of admin/streamlit_app.py::fetch_coverage.

    Returns a single flat dict keyed per segment (see _bump_coverage for shapes).
    Ganak's analyze() looks up keys by shape, so mixing segments in one dict is safe.

    Sources:
      - ingestion_triage_queue (non-rejected pending content)
      - pyq_bank_v2 (promoted live questions)
    """
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    coverage: dict[tuple, int] = {}

    # Triage queue (non-rejected) — pending content counts as coverage-in-flight
    try:
        rows = (
            db.table("ingestion_triage_queue")
            .select("raw_data")
            .eq("payload_type", "pyq")
            .neq("status", "rejected")
            .execute()
        ).data or []
        for row in rows:
            _bump_coverage(coverage, row.get("raw_data") or {})
    except Exception:
        pass

    # Live bank — approved + promoted questions
    try:
        rows = db.table("pyq_bank_v2").select("question_payload").execute().data or []
        for row in rows:
            _bump_coverage(coverage, row.get("question_payload") or {})
    except Exception:
        pass

    return coverage


def main() -> int:
    ap = argparse.ArgumentParser(description="Run আচার্য batch orchestrator.")
    ap.add_argument("--limit",   type=int, default=5, help="Max dispatches this run.")
    ap.add_argument(
        "--segment",
        choices=["school", "competitive", "entrance", "recruitment", "it"],
        default="school",
        help="'competitive' is legacy alias — prefer 'entrance' or 'recruitment'.",
    )
    ap.add_argument("--board",   default=None, help="Restrict to board (e.g. WBBSE).")
    ap.add_argument("--class",   dest="class_num", type=int, default=None, help="Restrict to class.")
    ap.add_argument("--per-run-mcqs", type=int, default=10)
    ap.add_argument("--delay",   type=float, default=3.0, help="Seconds between dispatches.")
    ap.add_argument("--ref",     default="main", help="Git ref for workflow_dispatch.")
    ap.add_argument("--dry-run", action="store_true", help="Preview without calling GitHub.")
    ap.add_argument("--json",    action="store_true", help="Emit BatchReceipt as JSON on stdout.")
    args = ap.parse_args()

    coverage = _fetch_coverage()
    receipt  = acharya.run_batch(
        coverage       = coverage,
        limit          = args.limit,
        segment_filter = args.segment,
        board_filter   = args.board,
        class_filter   = args.class_num,
        per_run_mcqs   = args.per_run_mcqs,
        delay_s        = args.delay,
        ref            = args.ref,
        dry_run        = args.dry_run,
    )

    if args.json:
        print(json.dumps(receipt.to_dict(), ensure_ascii=False, indent=2))

    if receipt.dispatched == 0 and receipt.failed == 0 and receipt.skipped == 0:
        return 2
    if receipt.dispatched == 0 and receipt.failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
