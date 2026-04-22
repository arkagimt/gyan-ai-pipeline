"""
Supabase Loader — ডেটাবেসে ডেটা পাঠানো
==========================================
Pushes সূত্রধর's StudyPackage into ingestion_triage_queue.
Uses the service_role key — bypasses RLS.

After pushing:
  - MCQs  → status='pending' in ingestion_triage_queue (payload_type='pyq')
  - Notes → status='pending' in ingestion_triage_queue (payload_type='material')

Human admin reviews at /admin/triage → approves → moves to
pyq_bank_v2 / study_materials tables.

Metadata round-trip (fixed 2026-04-20):
  The pipeline generates `vidushak_audit`, `safety_audit`, `bhashacharya_audit`,
  `source_type`, `source_label` into `StudyPackage.metadata`. Before this fix,
  `push()` read only `metadata.confidence` and dropped the rest — which meant
  the web trust-chip UI always saw empty audits. Now every audit object is
  forwarded into `raw_data` (for the triage queue JSON payload) and also
  mirrored onto the row-level `scope`/`nature` columns when available.

  Scaffold fields (`edit_log`, `last_reviewed_at`) are seeded empty/null here
  so the admin triage edit flow can append without a schema refactor.
"""

from __future__ import annotations
import json
import time
import requests

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, emit_progress
from models.schemas import StudyPackage, MCQItem, StudyNote, TaxonomySlice


REST_URL = f"{SUPABASE_URL}/rest/v1"
HEADERS  = {
    "apikey":        SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}


# ── Metadata forwarding ───────────────────────────────────────────────────────
# Keys from `StudyPackage.metadata` that must survive into the DB row so the
# web UI can render trust chips, provenance, and audit history.
_FORWARDED_METADATA_KEYS = (
    "vidushak_audit",
    "safety_audit",
    "bhashacharya_audit",
    "source_type",         # legacy Sarbagya fetch-method: pdf | url | llm_knowledge
    "source_label",        # human-readable (e.g. "WBBSE › Class 10 › Physical Science")
    "source_url",          # exact URL the PDF/text came from, if applicable
    "provenance_tier",     # SourceType enum value — credibility tier for Trust Chip
    "confidence",          # 0–100 quality score
    "scope_flag",          # "beyond_outline" for MCQs outside official skills outline
)


def _forward_metadata(package_metadata: dict | None) -> dict:
    """
    Extract the subset of StudyPackage.metadata that must be persisted to DB.
    Returns a fresh dict — safe to embed inside raw_data.
    """
    source = package_metadata or {}
    out: dict = {key: source[key] for key in _FORWARDED_METADATA_KEYS if key in source}
    # Scaffold fields — seeded for admin triage / edit flow.
    out.setdefault("edit_log", [])             # appended to by admin corrections
    out.setdefault("last_reviewed_at", None)   # stamped when admin approves
    return out


def _taxonomy_axes(taxonomy: TaxonomySlice) -> dict:
    """
    Extract scope + nature as primitive strings for DB columns and JSON payload.
    Returns an empty dict when axes aren't set (caller decides default behaviour).
    """
    axes: dict = {}
    if taxonomy.scope is not None:
        axes["scope"] = taxonomy.scope.value
    if taxonomy.nature is not None:
        axes["nature"] = taxonomy.nature.value
    return axes


# ── Build triage queue entries ────────────────────────────────────────────────

def _build_pyq_entry(
    mcq:               MCQItem,
    taxonomy:          TaxonomySlice,
    batch_id:          str,
    confidence:        int,
    package_metadata:  dict | None,
) -> dict:
    axes           = _taxonomy_axes(taxonomy)
    meta_forwarded = _forward_metadata(package_metadata)

    raw_data = {
        "question":          mcq.question,
        "options":           mcq.options.model_dump(),
        "correct":           mcq.correct,
        "reasoning_process": mcq.reasoning_process,
        "explanation":       mcq.explanation,
        "difficulty":        mcq.difficulty,
        "bloom_level":       mcq.bloom_level,
        "topic_tag":         mcq.topic_tag,
        "taxonomy_label":    taxonomy.label,
        "board":             taxonomy.board,
        "class_num":         taxonomy.class_num,
        "subject":           taxonomy.subject,
        "chapter":           taxonomy.chapter,
        "authority":         taxonomy.authority,
        "exam":              taxonomy.exam,
        "topic":             taxonomy.topic,
        "provider":          taxonomy.provider,
        # Phase 1.3 classification axes (mirrored from top-level DB columns)
        **axes,
        # Phase-7/5/17 audits + source provenance (trust chips + admin history)
        "metadata":          meta_forwarded,
    }

    entry = {
        "segment":          taxonomy.segment.value,
        "payload_type":     "pyq",
        "raw_data":         raw_data,
        "ai_accuracy_score": float(confidence),
        "validation_flags":  [],
        "status":            "pending",
        "batch_id":          batch_id,
    }
    # Top-level columns — populated only when the migration has run.
    # Older DB schemas silently ignore these (Supabase PostgREST rejects unknown
    # columns with 400; we protect against that with a try/fallback in _insert).
    if "scope" in axes:
        entry["scope"] = axes["scope"]
    if "nature" in axes:
        entry["nature"] = axes["nature"]
    return entry


def _build_material_entry(
    note:              StudyNote,
    taxonomy:          TaxonomySlice,
    batch_id:          str,
    confidence:        int,
    package_metadata:  dict | None,
) -> dict:
    axes           = _taxonomy_axes(taxonomy)
    meta_forwarded = _forward_metadata(package_metadata)

    raw_data = {
        "topic_title":     note.topic_title,
        "summary":         note.summary,
        "key_concepts":    note.key_concepts,
        "formulas":        note.formulas,
        "important_facts": note.important_facts,
        "examples":        note.examples,
        "memory_hooks":    note.memory_hooks,
        "taxonomy_label":  taxonomy.label,
        "board":           taxonomy.board,
        "class_num":       taxonomy.class_num,
        "subject":         taxonomy.subject,
        "chapter":         taxonomy.chapter,
        "authority":       taxonomy.authority,
        "exam":            taxonomy.exam,
        "topic":           taxonomy.topic,
        "provider":        taxonomy.provider,
        **axes,
        "metadata":        meta_forwarded,
    }

    entry = {
        "segment":          taxonomy.segment.value,
        "payload_type":     "material",
        "raw_data":         raw_data,
        "ai_accuracy_score": float(confidence),
        "validation_flags":  [],
        "status":            "pending",
        "batch_id":          batch_id,
    }
    if "scope" in axes:
        entry["scope"] = axes["scope"]
    if "nature" in axes:
        entry["nature"] = axes["nature"]
    return entry


# ── Insert with retry ─────────────────────────────────────────────────────────

def _strip_unknown_columns(entries: list[dict]) -> list[dict]:
    """
    Defensive fallback: if the DB hasn't had the scope/nature migration applied
    yet (scripts/add_scope_nature.sql), PostgREST returns HTTP 400 for unknown
    columns. Strip them and retry. raw_data.scope/nature are preserved either
    way for the admin UI.
    """
    cleaned = []
    for e in entries:
        e2 = {k: v for k, v in e.items() if k not in ("scope", "nature")}
        cleaned.append(e2)
    return cleaned


def _insert(entries: list[dict], label: str) -> list[str]:
    """Insert a batch into ingestion_triage_queue. Returns list of inserted IDs."""
    if not entries:
        return []

    payload         = entries
    retried_without = False

    for attempt in range(1, 4):
        try:
            resp = requests.post(
                f"{REST_URL}/ingestion_triage_queue",
                headers=HEADERS,
                json=payload,
                timeout=20,
            )
            if resp.status_code in (200, 201):
                inserted = resp.json()
                ids = [str(r.get("id", "")) for r in inserted if r.get("id")]
                emit_progress(f"[db] Inserted {len(ids)} {label} entries into triage queue")
                return ids

            # HTTP 400 + 'column "scope"/"nature"' → migration not applied yet.
            # Retry once without the new columns; raw_data still carries them.
            if (
                resp.status_code == 400
                and not retried_without
                and ("scope" in resp.text or "nature" in resp.text)
            ):
                emit_progress(
                    "[db] scope/nature columns missing — retrying without them "
                    "(run scripts/add_scope_nature.sql in Supabase to enable)"
                )
                payload = _strip_unknown_columns(payload)
                retried_without = True
                continue

            emit_progress(f"[db] Insert attempt {attempt}/3 failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            emit_progress(f"[db] Insert attempt {attempt}/3 exception: {e}")
        time.sleep(2 * attempt)

    emit_progress(f"[db] WARNING: Failed to insert {len(entries)} {label} entries after 3 attempts")
    return []


# ── Main loader function ──────────────────────────────────────────────────────

def push(package: StudyPackage) -> dict[str, list[str]]:
    """
    Push a StudyPackage to ingestion_triage_queue.
    Returns dict with lists of inserted IDs:
      { "pyq_ids": [...], "material_ids": [...] }
    """
    taxonomy   = package.taxonomy
    metadata   = package.metadata or {}
    confidence = int(metadata.get("confidence", 70))
    batch_id   = f"pipeline-{taxonomy.segment.value}-{int(time.time())}"

    # Build MCQ entries — every row now carries audit metadata + scope/nature
    pyq_entries = [
        _build_pyq_entry(mcq, taxonomy, batch_id, confidence, metadata)
        for mcq in package.mcqs
    ]

    # Build study note entries
    material_entries = [
        _build_material_entry(note, taxonomy, batch_id, confidence, metadata)
        for note in package.notes
    ]

    pyq_ids      = _insert(pyq_entries,      "MCQ")
    material_ids = _insert(material_entries, "study note")

    return {"pyq_ids": pyq_ids, "material_ids": material_ids}
