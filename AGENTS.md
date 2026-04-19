# Gyan AI — Agent Registry

Canonical mapping between the 9 agents advertised on **gyanagent.in/about** and
their implementation in this repo. Keep this file in sync whenever an agent is
added, renamed, extracted, or repositioned.

---

## Active Agents (pipeline)

| Website Name | Bengali | Role | Implementation | Notes |
|---|---|---|---|---|
| **Sarbagya** | সর্বজ্ঞ | The Scout & Ingestor | `agents/sarbagya.py` + `loaders/{pdf,web,ocr,supabase_storage}_loader.py` | Extracts facts/concepts from source material. Phase 6: Bengali textbooks go through Marker+Surya OCR (offline, via `scripts/ocr_textbook.py` + `ocr_textbook.yml` workflow). Ingest runs read the cached `.txt` sibling — no OCR inside the 15-min ingest window. |
| **Sutradhar** | সূত্রধর | The Conceptual Guide | `agents/sutradhar.py` | Synthesizes study notes + MCQs from validated content. |
| **Vidushak** | বিদূষক | The Adversarial Critic | `agents/vidushak.py` | Self-critique pass on Sutradhar's MCQs. v1 checks: wrong-answer, two-correct, accidentally-correct distractor, ambiguous, language/age mismatch. v2 (Phase 7, RAG grounding): SOURCE_DISCONNECT check — verifies the correct answer is traceable to a fact in Sarbagya's extract; corpus-anchored repair loop when ungrounded. Emits `vidushak_audit` into `StudyPackage.metadata`. |
| **Chitragupta** | চিত্রগুপ্ত | The Quality Gatekeeper | `agents/chitragupta.py` + `admin/streamlit_app.py` triage page | Two faces: (1) pre-generation content validation (code), (2) admin-triage gatekeeping before DB promotion (Streamlit + DB rules). |
| **Dharmarakshak** | ধর্মরক্ষক | The Safety Guardian | `agents/dharmarakshak.py` | Post-generation safety gate. Uses Llama Guard 3 (Groq) to classify against the S1/S4/S8/S10/S11/S12/S13 hazard taxonomy + heuristic wrong-language/verbose-stem checks. Drops blocked MCQs, attaches `safety_audit` to `StudyPackage.metadata` for admin review. |
| **Sanjaya** | সঞ্জয় | The Omniscient Chronicler | `db/memory.py` (legacy location — to rename `agents/sanjaya.py` post-Phase-6) | Passive observer — tracks milestones, emits alerts when thresholds cross. Also owns dedup-memory lookups (`check_existing_mcqs`). No LLM. |

## Active Agents (analytics)

| Website Name | Bengali | Role | Implementation | Notes |
|---|---|---|---|---|
| **Ganak** | গণক | The Analyst | `agents/ganak.py` (consumed by `admin/streamlit_app.py` Priority panel) | Heuristic priority analyst — coverage gaps, class priority, board weighting, zero-coverage boost. No LLM. |
| **Acharya** | আচার্য | The Curriculum Orchestrator | `agents/acharya.py` + `scripts/run_acharya.py` + Command Centre panel | Phase 10. Reads গণক's top-N priorities → dispatches `ingest_school/competitive/it.yml` workflows via GitHub Actions API. Stateless, rate-limited, dry-run previewable. Also runnable from cron via `python -m scripts.run_acharya`. No LLM. |

## Planned Agents (milestone-gated)

| Website Name | Bengali | Role | Trigger | Notes |
|---|---|---|---|---|
| **Anveshak** | অন্বেষক | Semantic Search | SC-002 @ 1000 MCQs | pgvector embeddings, concept-based question discovery. |
| **Betal** | বেতাল | Student Doubt Solver | SC-003 @ 2500 MCQs | PydanticAI-powered 1:1 doubt agent. |
| **Narad** | নারদ | Spaced-Repetition Tutor | SC-003 @ 2500 MCQs | Forgetting-curve scheduling + personalized review. |

---

## Data Flow (Active Pipeline)

```
TaxonomySlice
    │
    ▼
┌───────────────┐   RawExtract   ┌────────────────┐
│   Sarbagya    │ ─────────────► │   Chitragupta  │
│   (Scout)     │                │  (Pre-gen val.)│
└───────────────┘                └────────────────┘
                                         │
                                         │ ValidationReport
                                         ▼
                                 ┌────────────────┐
                                 │   Sutradhar    │
                                 │   (Creator)    │
                                 └────────────────┘
                                         │
                                         │ StudyOutput (notes + MCQs)
                                         ▼
                                 ┌────────────────┐
                                 │   Vidushak     │
                                 │ (MCQ critique) │
                                 └────────────────┘
                                         │
                                         │ StudyPackage (verified)
                                         ▼
                                 ┌────────────────┐
                                 │ Dharmarakshak  │
                                 │ (safety gate)  │ ◄── Llama Guard 3
                                 └────────────────┘
                                         │
                                         │ safe_mcqs + safety_audit
                                         ▼
                                 ┌────────────────┐
                                 │ Triage Queue   │ ◄── Chitragupta admin face
                                 │ (Supabase)     │     (Streamlit review)
                                 └────────────────┘
                                         │
                                         ▼
                                     pyq_bank_v2
                                     (live)

Sanjaya watches from above — emits milestone alerts after each push.
Ganak reads from pyq_bank_v2 + curriculum_sources to surface next priorities.
```

---

## Naming Rules

1. **File name = agent_id** (lowercase romanised Bengali). Examples: `sarbagya.py`, `sutradhar.py`, `vidushak.py`, `chitragupta.py`, `ganak.py`.
2. **Docstring line 1 = Bengali name + tagline**. Makes the file's identity
   visible at a glance when grepping or browsing GitHub.
3. **emit_agent() uses Bengali Unicode** for UI output. Never the romanised name.
4. **Never embed one agent inside another.** If you find yourself writing a
   second `_VERIFIER_SYSTEM` inside another file, it's a new agent — give it
   its own file and add it to this registry.
