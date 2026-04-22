# `sources/llm_seed/` — LLM-authored seed content

**Tier:** `source_type = "llm_knowledge"` (lowest-trust ingestion tier)
**Purpose:** Bootstrap coverage for exams where we don't yet have an
authoritative PDF corpus — AWS CCP, Azure AZ-900, GCP ACE, etc.

---

## Why this tier exists

Our three trust tiers (ranked high→low):

| `source_type`        | Origin                               | Student-facing disclosure          |
|----------------------|--------------------------------------|-------------------------------------|
| `textbook_ocr`       | Board-approved textbook, OCR'd       | "From your textbook"                |
| `web_scraped`        | Official exam-provider documentation | "From Microsoft Learn" (etc.)       |
| **`llm_knowledge`**  | **Frontier LLM + human review**      | **Trust Chip: "AI-generated"**      |

The existing pipeline (`agents/sarbagya.py → chitragupta.py → vidushak.py →
sutradhar.py`) treats `llm_knowledge` identically to the other tiers — same
schema, same audit gates — *except* that downstream UI shows a distinct
Trust Chip so students know the provenance.

## Reproducible workflow (no API cost, high quality)

1. **Generate** with Google AI Studio (Gemini 2.5 Pro, free tier) using
   the domain-batched prompt template. See `az-900/` as canonical example:
   - Split the target exam's skills outline into 3 domains.
   - Ask for ~33 MCQs + 3 notes per domain in one prompt (fresh chat each).
   - Request coverage_tables so the model self-polices sub-objective spread.
   - Request SELF_AUDIT JSON block so shortfalls surface up front.
2. **Top-up** any short batches in a follow-up prompt with an explicit
   regenerate-these-6 patch list.
3. **Save verbatim** pastes as `raw-round-N.json` (do not hand-edit).
4. **Merge** via `<exam>/merge_seed.py`:
   - Applies FIXES by stem substring.
   - Auto-prefixes explanations of "beyond skills outline" MCQs with a
     student-visible warning (see below).
   - Emits `<exam>-v1.json` + `meta.known_issues[]` manifest.
5. **Audit gate** — before pilot users see any of this content, run
   `python -m sources.llm_seed.audit <exam>` (e.g. `az-900`). This:
   - batches the seed's MCQs through `vidushak.verify_and_repair()`,
   - writes a timestamped `audit-<ts>.json` report,
   - flips the seed's `meta.audit_gate.status` to `"passed"` only on zero
     findings; anything else becomes `"needs-review"` and blocks pilot use.
   Requires `GROQ_API_KEY`. Add a new exam by registering its `TaxonomySlice`
   in `EXAM_TAXONOMIES` inside `audit.py`.

## The "beyond outline" warning pattern

Some MCQs test concepts that sit *just outside* the official skills outline
but still appear on real proctored exams (e.g. AZ-900 + Azure Landing Zones /
Cloud Adoption Framework). Hiding them would produce fragile prep.

The merge script injects a student-visible warning at the front of the
`explanation` field:

```
⚠️ Beyond skills outline — may still appear on the real exam.
```

Zero schema change required. Admin side also gets a `known_issues[]` entry
in the meta block so audit dashboards can list them explicitly.

## Directory layout

```
llm_seed/
├── README.md                 ← this file
├── az-900/
│   ├── raw-round-1.json      ← verbatim Gemini paste, round 1 (3 batches)
│   ├── raw-round-2.json      ← verbatim Gemini paste, round 2 (fixes + top-ups)
│   ├── merge_seed.py         ← deterministic merger — idempotent
│   └── az-900-v1.json        ← ingestion-ready artifact (committed)
├── aws-ccp/                  ← TODO: same pattern
└── gcp-ace/                  ← TODO: same pattern
```

## What counts as a valid merge output

- All MCQs conform to `models.schemas.MCQItem` (question/options/correct/
  reasoning_process/explanation/difficulty/bloom_level/topic_tag).
- All notes conform to `models.schemas.StudyNote`.
- `meta.source_type == "llm_knowledge"` (non-negotiable).
- `meta.pipeline_ingest` carries taxonomy hints (segment, authority, exam).
- Any `known_issues[].flag == "beyond_outline"` entry has both a `seq` and
  a matching warning-prefix in the corresponding MCQ's `explanation`.
