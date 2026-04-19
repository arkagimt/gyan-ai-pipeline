"""
scripts/run_vaidya.py
======================
CLI wrapper around agents.vaidya.run_healthcheck().

Usage:
    python -m scripts.run_vaidya              # human-readable
    python -m scripts.run_vaidya --json       # machine-readable

Exit codes:
    0 — all checks green
    1 — one or more checks failed
    2 — env-var misconfig (couldn't even start)
"""

from __future__ import annotations

import argparse
import json
import sys

from agents import vaidya


def main() -> int:
    ap = argparse.ArgumentParser(description="Run বৈদ্য pipeline health check.")
    ap.add_argument("--json", action="store_true", help="Emit HealthReport as JSON on stdout.")
    args = ap.parse_args()

    try:
        report = vaidya.run_healthcheck()
    except Exception as e:
        print(f"fatal: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print()
        print(f"{'✓' if report.all_ok else '✗'} Vaidya Health Report — {report.ended_at}")
        print(f"  fail_count: {report.fail_count}")
        for c in report.checks:
            icon = "✓" if c.ok else ("⊘" if c.skipped else "✗")
            lat  = f"{c.latency_ms:.0f}ms" if c.latency_ms is not None else "    —"
            print(f"  {icon}  {c.name:<14}  {lat:>8}  {c.detail}")
        print()

    return 0 if report.all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
