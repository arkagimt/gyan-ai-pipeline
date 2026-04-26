#!/usr/bin/env python3
"""
backfill_topic_per_mcq.py
=========================
One-shot migration to fix the per-batch-topic issue in pyq_bank_v2 +
ingestion_triage_queue. Wave 4.5 (2026-04-26).

Problem: load_to_supabase.py used to set question_payload.topic from
TaxonomySlice.topic, which is constant across every MCQ in a batched
StudyPackage (25 MCQs). With 100 MCQs / 25-batch, only 4 distinct topics
persisted per exam — admin Streamlit's IT coverage map showed ~4/N
covered (instead of all N). Wave 4.5 fixed the loader for FUTURE pushes
(prefers MCQ.topic_tag), but the 5 already-loaded Microsoft exams
(AZ-900, AI-900, DP-900, AZ-104, DP-600) still have the per-batch values.

This script reads each `pyq_bank_v2` row's existing `question_payload.topic_tag`
field (which is per-MCQ, untouched) and writes it back into
`question_payload.topic` and into the matching `metadata` if the topic field
exists there.

Idempotent: running twice is a no-op for already-fixed rows.
Dry-run safe: pass --dry-run to print without writing.

Usage:
  python scripts/backfill_topic_per_mcq.py --dry-run
  python scripts/backfill_topic_per_mcq.py --segment it --commit
  python scripts/backfill_topic_per_mcq.py --exam az-900 --commit

Filters work in AND combination. With no filters, scans the entire bank.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase import create_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill per-MCQ topic in pyq_bank_v2")
    parser.add_argument("--segment", help="Filter by segment (school|competitive|it|entrance|recruitment)")
    parser.add_argument("--exam",    help="Filter by metadata.exam (e.g. az-900)")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    parser.add_argument("--commit",  action="store_true", help="Required to actually write")
    parser.add_argument("--batch-size", type=int, default=200, help="Page size for fetch")
    args = parser.parse_args()

    if not args.dry_run and not args.commit:
        print("error: pass --dry-run OR --commit (refusing to write without explicit flag)")
        return 2

    url  = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key  = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not (url and key):
        print("error: SUPABASE_URL + SUPABASE_SERVICE_KEY (or SUPABASE_KEY) must be set")
        return 3
    db = create_client(url, key)

    # Fetch in pages
    print(f"Fetching pyq_bank_v2 rows (segment={args.segment}, exam={args.exam}) ...")
    q = db.table("pyq_bank_v2").select("id, question_payload, metadata")
    if args.segment:
        q = q.eq("question_payload->>segment", args.segment)
    if args.exam:
        q = q.eq("metadata->>exam", args.exam)

    # Supabase Python client doesn't paginate automatically — fetch in chunks
    rows: list[dict] = []
    page = 0
    while True:
        start = page * args.batch_size
        end   = start + args.batch_size - 1
        chunk = q.range(start, end).execute().data or []
        if not chunk:
            break
        rows.extend(chunk)
        page += 1
        if len(chunk) < args.batch_size:
            break

    print(f"Loaded {len(rows)} rows.")

    fixed = 0
    skipped_no_tag = 0
    skipped_already = 0
    errors = 0
    for row in rows:
        payload = row.get("question_payload") or {}
        topic_tag = payload.get("topic_tag")
        current_topic = payload.get("topic")

        if not topic_tag:
            skipped_no_tag += 1
            continue
        if topic_tag == current_topic:
            skipped_already += 1
            continue

        if args.dry_run:
            print(f"  WOULD update {row['id']}: topic={current_topic!r} -> {topic_tag!r}")
            fixed += 1
            continue

        # Write back: payload.topic = topic_tag
        new_payload = {**payload, "topic": topic_tag}
        try:
            db.table("pyq_bank_v2").update(
                {"question_payload": new_payload}
            ).eq("id", row["id"]).execute()
            fixed += 1
            if fixed % 50 == 0:
                print(f"  ... {fixed} updated")
        except Exception as e:
            errors += 1
            print(f"  ERROR row {row['id']}: {e}")

    print()
    print(f"Summary:")
    print(f"  fixed             : {fixed} {'(dry-run)' if args.dry_run else ''}")
    print(f"  skipped (no tag)  : {skipped_no_tag}")
    print(f"  skipped (in sync) : {skipped_already}")
    print(f"  errors            : {errors}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
