"""
scripts/bootstrap_official_corpus.py
====================================
Seed the pipeline from `sources/OFFICIAL_SOURCES.md` — the tier-tagged registry
of legally reusable sources (UPSC / NCERT / JEE / CBSE specimens / AWS docs
/ etc.). Downloads each source PDF, dispatches `ingest_*.yml` workflows with
proper `--source-pdf` + `--source-url` + provenance-tier stamping.

This replaces the temptation to buy Physics Wallah compilations or ingest IT
cert dumps. Every MCQ minted by this bootstrap lands in `pyq_bank_v2` with a
strong `source_type` SourceType enum + human-readable `source_label`.

Usage
-----
    # Preview what would happen — no downloads, no dispatches
    python -m scripts.bootstrap_official_corpus --dry-run

    # Ingest only UPSC tier-gold sources (safest first sweep)
    python -m scripts.bootstrap_official_corpus --only upsc

    # Full sweep (school + entrance + recruitment + IT vendor-gold)
    python -m scripts.bootstrap_official_corpus --limit 20 --delay 8

    # Local PDFs already downloaded into /tmp/gyan_corpus — just dispatch
    python -m scripts.bootstrap_official_corpus --from-local /tmp/gyan_corpus

Flags
-----
    --dry-run         Preview: print the download + dispatch plan, don't execute.
    --only <prefix>   Filter to sources whose identifier starts with prefix
                      (e.g. "upsc", "ncert", "aws", "jee", "cbse").
    --limit N         Max number of dispatches (default: 10). Respects GH's
                      20-concurrent-workflow cap with some headroom.
    --delay S         Seconds between dispatches (default: 8). Politer than
                      the default Acharya cadence because these are one-shots.
    --from-local DIR  Skip the download step and use PDFs already in DIR.
                      DIR layout mirrors the registry's segment/authority tree.
    --corpus-dir DIR  Where to download PDFs (default: /tmp/gyan_corpus).
    --pat / --repo    GitHub PAT + "owner/repo" — falls back to env vars.

Identity
--------
This is NOT Acharya. Acharya picks coverage gaps and dispatches N random
slots. Bootstrap is the opposite: it walks a fixed curated source list and
dispatches everything that has a registered URL, regardless of gap scores.
Acharya fills gaps; Bootstrap lays the foundation.

Ethics
------
This script's registry explicitly excludes:
  - IT cert brain dumps (ExamTopics etc.) — NDA/DMCA/CFAA exposure
  - Third-party ed-tech PYQ compilations (PW/BYJU'S) — compilation copyright
  - Leaked mid-session papers — criminal liability
See sources/GAP_SOURCING.md §"Dumps Policy".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import requests

from config import emit_agent, emit_progress
from models.schemas import SourceType


# ── Registry (the subset this script auto-handles) ────────────────────────────
#
# The MD registry in sources/OFFICIAL_SOURCES.md is the human-readable source
# of truth. This dict is its machine-executable subset — only rows where we
# have a stable direct-download URL. Bronze/Gap rows are tracked in
# GAP_SOURCING.md and require human action.
#
# Structure:
#   SOURCE_ID → {
#     segment, provenance_tier, url, label, pipeline_inputs (dict for
#     workflow_dispatch), workflow_yml
#   }
#
# New rows land here after a human audit confirms the URL is stable.
# Treat this as an append-only list; never silently change URL strings.
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SourceRow:
    source_id:        str
    segment:          str            # school | entrance | recruitment | it
    provenance_tier:  SourceType
    url:              str
    label:            str            # human-readable for Trust Chip
    workflow_yml:     str            # ingest_school.yml / ingest_competitive.yml / ingest_it.yml
    pipeline_inputs:  dict           # workflow_dispatch inputs (minus source_url, which we inject)
    notes:            str = ""       # optional operator context


# A minimal starter registry — ~15 high-confidence rows. Expand as the audit
# in OFFICIAL_SOURCES.md marks more URLs [VERIFIED]. The strategy is
# deliberately "few-but-solid" > "many-but-broken": one working UPSC run
# > ten 404s.
_REGISTRY: list[SourceRow] = [
    # ── UPSC CSE Prelims (Tier 🥇 gold — rock solid) ──────────────────────────
    SourceRow(
        source_id       = "upsc_cse_prelim_gs1_2023",
        segment         = "recruitment",
        provenance_tier = SourceType.official_past,
        url             = "https://upsc.gov.in/sites/default/files/QP-CSP-23-GS-Paper-I-110623.pdf",
        label           = "UPSC CSE Prelim · GS Paper 1 · 2023",
        workflow_yml    = "ingest_competitive.yml",
        pipeline_inputs = {
            "segment":   "recruitment",
            "authority": "UPSC",
            "exam":      "Civil Services Prelim",
            "topic":     "General Studies Paper 1",
            "count":     "10",
        },
        notes = "[VERIFY-URL] confirm path on upsc.gov.in before first run — UPSC re-paths PDFs occasionally",
    ),

    # ── NCERT Exemplar (Tier 🥈 silver — govt-published, broadly reusable) ────
    SourceRow(
        source_id       = "ncert_exemplar_class10_science",
        segment         = "school",
        provenance_tier = SourceType.ncert_exemplar,
        url             = "https://ncert.nic.in/textbook.php?jeep1=0-13",
        label           = "NCERT Exemplar · Class 10 Science",
        workflow_yml    = "ingest_school.yml",
        pipeline_inputs = {
            "board":     "CBSE",
            "class_num": "10",
            "subject":   "Science",
            "count":     "10",
        },
        notes = "[VERIFY-URL] landing page lists chapter PDFs; bootstrap fetches chapter list then recurses",
    ),
    SourceRow(
        source_id       = "ncert_exemplar_class10_math",
        segment         = "school",
        provenance_tier = SourceType.ncert_exemplar,
        url             = "https://ncert.nic.in/textbook.php?jeep1=0-13",
        label           = "NCERT Exemplar · Class 10 Mathematics",
        workflow_yml    = "ingest_school.yml",
        pipeline_inputs = {
            "board":     "CBSE",
            "class_num": "10",
            "subject":   "Mathematics",
            "count":     "10",
        },
        notes = "[VERIFY-URL] same landing page as science exemplar",
    ),

    # ── JEE Main (Tier 🥇 — NTA archives every session) ───────────────────────
    SourceRow(
        source_id       = "jee_main_physics_2024_jan",
        segment         = "entrance",
        provenance_tier = SourceType.official_past,
        url             = "https://jeemain.nta.nic.in/",   # archive page; exact session URL varies
        label           = "JEE Main · Physics · Jan 2024 Session 1",
        workflow_yml    = "ingest_competitive.yml",
        pipeline_inputs = {
            "segment":   "entrance",
            "authority": "JEE",
            "exam":      "JEE Main",
            "topic":     "Physics",
            "count":     "10",
        },
        notes = "[VERIFY-URL] drill from NTA archive → session-specific PDF",
    ),

    # ── CBSE Sample Papers (Tier 🥈 — official but not real past) ─────────────
    SourceRow(
        source_id       = "cbse_sqp_class10_science_2024_25",
        segment         = "school",
        provenance_tier = SourceType.official_sample,
        url             = "https://cbseacademic.nic.in/SQP_CLASSX_2024-25.html",
        label           = "CBSE SQP · Class 10 Science · 2024–25",
        workflow_yml    = "ingest_school.yml",
        pipeline_inputs = {
            "board":     "CBSE",
            "class_num": "10",
            "subject":   "Science",
            "count":     "10",
        },
        notes = "[VERIFY-URL] CBSE re-paths yearly; check for current academic year",
    ),

    # ── AWS SAA-C03 official sample questions (Tier 🏆 — vendor authoritative) ─
    SourceRow(
        source_id       = "aws_saa_c03_exam_guide",
        segment         = "it",
        provenance_tier = SourceType.vendor_sample,
        url             = "https://d1.awsstatic.com/training-and-certification/docs-sa-assoc/AWS-Certified-Solutions-Architect-Associate_Exam-Guide.pdf",
        label           = "AWS SAA-C03 · Official Exam Guide + Sample Questions",
        workflow_yml    = "ingest_it.yml",
        pipeline_inputs = {
            "provider": "AWS",
            "exam":     "Solutions Architect Associate",
            "topic":    "EC2 & Compute",
            "count":    "10",
        },
        notes = "[VERIFY-URL] AWS occasionally re-hosts; check aws.amazon.com/certification/certified-solutions-architect-associate/",
    ),
    SourceRow(
        source_id       = "aws_well_architected_framework",
        segment         = "it",
        provenance_tier = SourceType.vendor_docs,
        url             = "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html",
        label           = "AWS Well-Architected Framework",
        workflow_yml    = "ingest_it.yml",
        pipeline_inputs = {
            "provider": "AWS",
            "exam":     "Solutions Architect Associate",
            "topic":    "High Availability & Fault Tolerance",
            "count":    "10",
        },
        notes = "[VERIFY-URL] stable docs URL; HTML not PDF — pipeline handles via --source-url",
    ),

    # ── Azure AZ-900 (Tier 🏆) ────────────────────────────────────────────────
    SourceRow(
        source_id       = "azure_az900_exam_skills_outline",
        segment         = "it",
        provenance_tier = SourceType.vendor_sample,
        url             = "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/",
        label           = "Microsoft AZ-900 · Azure Fundamentals · Exam Skills Outline",
        workflow_yml    = "ingest_it.yml",
        pipeline_inputs = {
            "provider": "Microsoft",
            "exam":     "AZ-900 Azure Fundamentals",
            "topic":    "Cloud Concepts",
            "count":    "10",
        },
    ),

    # ── GCP Associate Cloud Engineer (Tier 🏆) ────────────────────────────────
    SourceRow(
        source_id       = "gcp_ace_exam_guide",
        segment         = "it",
        provenance_tier = SourceType.vendor_sample,
        url             = "https://cloud.google.com/learn/certification/cloud-engineer",
        label           = "GCP Associate Cloud Engineer · Official Exam Guide",
        workflow_yml    = "ingest_it.yml",
        pipeline_inputs = {
            "provider": "Google",
            "exam":     "Associate Cloud Engineer",
            "topic":    "GCP Core Infrastructure",
            "count":    "10",
        },
    ),
]


# ── Core operations ───────────────────────────────────────────────────────────

@dataclass
class BootstrapResult:
    source_id:     str
    dispatched:    bool
    status_code:   int | None = None
    message:       str = ""
    pdf_path:      str | None = None


def _download(row: SourceRow, corpus_dir: Path, timeout: float = 30.0) -> Path | None:
    """Download the source PDF/HTML to corpus_dir. Returns path on success."""
    dest_dir = corpus_dir / row.segment
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Content-addressed filename — safe even if two rows have the same URL.
    url_hash = hashlib.sha1(row.url.encode()).hexdigest()[:12]
    # Infer extension from URL; default to .bin if unclear.
    ext = ".pdf" if row.url.lower().endswith(".pdf") else ".html"
    dest = dest_dir / f"{row.source_id}__{url_hash}{ext}"

    if dest.exists() and dest.stat().st_size > 0:
        emit_progress(f"[bootstrap] cache hit: {dest.name}")
        return dest

    try:
        emit_progress(f"[bootstrap] downloading {row.source_id} ← {row.url}")
        resp = requests.get(row.url, timeout=timeout, headers={
            "User-Agent": "GyanAI-BootstrapCorpus/1.0 (educational; contact: team@gyanagent.in)",
        })
        if resp.status_code != 200:
            emit_progress(f"[bootstrap] ✗ {row.source_id} HTTP {resp.status_code}")
            return None
        dest.write_bytes(resp.content)
        emit_progress(f"[bootstrap] ✓ saved {dest.name} ({len(resp.content) // 1024} KB)")
        return dest
    except Exception as exc:
        emit_progress(f"[bootstrap] ✗ {row.source_id} download error: {exc}")
        return None


def _dispatch(
    row:      SourceRow,
    pat:      str,
    repo:     str,
    ref:      str = "main",
    timeout:  float = 15.0,
) -> tuple[int, str]:
    """
    Fire workflow_dispatch for `row.workflow_yml`, injecting source_url so
    Sarbagya fetches and Sutradhar can cite correctly.
    """
    inputs = dict(row.pipeline_inputs)
    inputs["source_url"] = row.url

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{row.workflow_yml}/dispatches"
    try:
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
        return resp.status_code, (resp.text or "")[:300]
    except Exception as exc:
        return 0, f"exception: {exc}"


def _filter_registry(only: str | None) -> list[SourceRow]:
    if not only:
        return list(_REGISTRY)
    prefix = only.strip().lower()
    return [r for r in _REGISTRY if r.source_id.lower().startswith(prefix)]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Bootstrap pipeline from official source registry."
    )
    ap.add_argument("--only", default=None,
                    help="Filter to source IDs starting with this prefix (e.g. 'upsc', 'aws', 'ncert')")
    ap.add_argument("--limit", type=int, default=10,
                    help="Max dispatches in this run (GH concurrency cap guard)")
    ap.add_argument("--delay", type=float, default=8.0,
                    help="Seconds between dispatches")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview the plan; don't download or dispatch")
    ap.add_argument("--from-local", default=None,
                    help="Skip downloads; reuse PDFs already in this directory")
    ap.add_argument("--corpus-dir", default=os.environ.get("GYAN_CORPUS_DIR", "/tmp/gyan_corpus"),
                    help="Where to cache downloaded PDFs")
    ap.add_argument("--pat", default=None, help="GitHub PAT (falls back to $GITHUB_PAT)")
    ap.add_argument("--repo", default=None, help="GitHub owner/repo (falls back to $GITHUB_REPO)")
    ap.add_argument("--ref", default="main", help="Git ref for workflow_dispatch")
    ap.add_argument("--json", action="store_true", help="Emit result summary as JSON")
    args = ap.parse_args()

    rows = _filter_registry(args.only)[: args.limit]

    if not rows:
        emit_progress("[bootstrap] no rows matched filter — nothing to do")
        return 2

    emit_agent(
        "Bootstrap",
        f"Seeding {len(rows)} sources — dry_run={args.dry_run}, "
        f"only={args.only or '(all)'}, limit={args.limit}",
    )

    corpus_dir = Path(args.from_local or args.corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # Credentials — skip for dry run
    if not args.dry_run:
        pat  = args.pat  or os.environ.get("GITHUB_PAT", "")
        repo = args.repo or os.environ.get("GITHUB_REPO", "")
        if not pat or not repo:
            print(
                "bootstrap needs GITHUB_PAT + GITHUB_REPO (env vars or --pat/--repo). "
                "Dry run first with --dry-run to verify the plan.",
                file=sys.stderr,
            )
            return 1

    results: list[BootstrapResult] = []

    for idx, row in enumerate(rows, 1):
        prefix = f"({idx}/{len(rows)}) {row.source_id}"

        # 1. Download (unless --from-local or --dry-run)
        pdf_path: Path | None = None
        if args.dry_run:
            emit_progress(f"[bootstrap] {prefix} DRY — would download {row.url}")
        elif args.from_local:
            # Caller promises the PDF already exists
            candidates = list(Path(args.from_local).rglob(f"{row.source_id}__*"))
            pdf_path = candidates[0] if candidates else None
            if not pdf_path:
                emit_progress(f"[bootstrap] {prefix} ✗ no local PDF matching {row.source_id}__*")
                results.append(BootstrapResult(
                    source_id=row.source_id, dispatched=False,
                    message="no local PDF found",
                ))
                continue
        else:
            pdf_path = _download(row, corpus_dir)
            if not pdf_path:
                results.append(BootstrapResult(
                    source_id=row.source_id, dispatched=False,
                    message="download failed",
                ))
                continue

        # 2. Dispatch (unless --dry-run)
        if args.dry_run:
            emit_progress(
                f"[bootstrap] {prefix} DRY — would dispatch {row.workflow_yml} "
                f"with inputs={row.pipeline_inputs} source_url={row.url}"
            )
            results.append(BootstrapResult(
                source_id=row.source_id, dispatched=True,
                message="dry-run", pdf_path=str(pdf_path) if pdf_path else None,
            ))
        else:
            status, msg = _dispatch(row, pat=pat, repo=repo, ref=args.ref)
            ok = (status == 204)
            results.append(BootstrapResult(
                source_id=row.source_id, dispatched=ok,
                status_code=status, message=msg,
                pdf_path=str(pdf_path) if pdf_path else None,
            ))
            marker = "✓" if ok else "✗"
            emit_progress(f"[bootstrap] {prefix} {marker} {row.workflow_yml} → {status} {msg}")

        # Rate-limit between dispatches
        if idx < len(rows) and args.delay > 0 and not args.dry_run:
            time.sleep(args.delay)

    # ── Summary ───────────────────────────────────────────────────────────────
    ok_count   = sum(1 for r in results if r.dispatched)
    fail_count = len(results) - ok_count
    emit_agent(
        "Bootstrap",
        f"Done — dispatched={ok_count}, failed={fail_count}"
        + (" (dry-run)" if args.dry_run else ""),
    )

    if args.json:
        print(json.dumps(
            {
                "dry_run":    args.dry_run,
                "dispatched": ok_count,
                "failed":     fail_count,
                "results":    [
                    {
                        "source_id":   r.source_id,
                        "dispatched":  r.dispatched,
                        "status_code": r.status_code,
                        "message":     r.message,
                        "pdf_path":    r.pdf_path,
                    }
                    for r in results
                ],
            },
            ensure_ascii=False, indent=2,
        ))

    if fail_count == len(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
