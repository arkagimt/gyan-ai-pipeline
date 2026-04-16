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


# ── Build triage queue entries ────────────────────────────────────────────────

def _build_pyq_entry(mcq: MCQItem, taxonomy: TaxonomySlice, batch_id: str, confidence: int) -> dict:
    return {
        "segment":          taxonomy.segment.value,
        "payload_type":     "pyq",
        "raw_data": {
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
        },
        "ai_accuracy_score": float(confidence),
        "validation_flags":  [],
        "status":            "pending",
        "batch_id":          batch_id,
    }


def _build_material_entry(note: StudyNote, taxonomy: TaxonomySlice, batch_id: str, confidence: int) -> dict:
    return {
        "segment":          taxonomy.segment.value,
        "payload_type":     "material",
        "raw_data": {
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
        },
        "ai_accuracy_score": float(confidence),
        "validation_flags":  [],
        "status":            "pending",
        "batch_id":          batch_id,
    }


# ── Insert with retry ─────────────────────────────────────────────────────────

def _insert(entries: list[dict], label: str) -> list[str]:
    """Insert a batch into ingestion_triage_queue. Returns list of inserted IDs."""
    if not entries:
        return []

    for attempt in range(1, 4):
        try:
            resp = requests.post(
                f"{REST_URL}/ingestion_triage_queue",
                headers=HEADERS,
                json=entries,
                timeout=20,
            )
            if resp.status_code in (200, 201):
                inserted = resp.json()
                ids = [str(r.get("id", "")) for r in inserted if r.get("id")]
                emit_progress(f"[db] Inserted {len(ids)} {label} entries into triage queue")
                return ids
            else:
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
    confidence = int(package.metadata.get("confidence", 70))
    batch_id   = f"pipeline-{taxonomy.segment.value}-{int(time.time())}"

    # Build MCQ entries
    pyq_entries = [
        _build_pyq_entry(mcq, taxonomy, batch_id, confidence)
        for mcq in package.mcqs
    ]

    # Build study note entries
    material_entries = [
        _build_material_entry(note, taxonomy, batch_id, confidence)
        for note in package.notes
    ]

    pyq_ids      = _insert(pyq_entries,      "MCQ")
    material_ids = _insert(material_entries, "study note")

    return {"pyq_ids": pyq_ids, "material_ids": material_ids}
