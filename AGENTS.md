# Gyan AI — Agent Registry

Canonical mapping between the 9 agents advertised on **gyanagent.in/about** and
their implementation in this repo. Keep this file in sync whenever an agent is
added, renamed, extracted, or repositioned.

---

## Active Agents (pipeline)

| Website Name | Bengali | Role | Implementation | Notes |
|---|---|---|---|---|
| **Sarbagya** | সর্বজ্ঞ | The Scout & Ingestor | `agents/sarbagya.py` | Extracts facts/concepts from source material (PDF/URL/LLM knowledge). |
| **Sutradhar** | সূত্রধর | The Conceptual Guide | `agents/sutradhar.py` | Synthesizes study notes + MCQs from validated content. |
| **Vidushak** | বিদূষক | The Adversarial Critic | `agents/vidushak.py` | Self-critique pass on Sutradhar's MCQs. Flags hallucinations, wrong answers, accidentally-correct distractors, language/age mismatches. |
| **Chitragupta** | চিত্রগুপ্ত | The Quality Gatekeeper | `agents/chitragupta.py` + `admin/streamlit_app.py` triage page | Two faces: (1) pre-generation content validation (code), (2) admin-triage gatekeeping before DB promotion (Streamlit + DB rules). |
| **Sanjaya** | সঞ্জয় | The Omniscient Chronicler | `db/memory.py` | Passive observer — tracks milestones, emits alerts when thresholds cross. No LLM. |

## Active Agents (analytics)

| Website Name | Bengali | Role | Implementation | Notes |
|---|---|---|---|---|
| **Ganak** | গণক | The Analyst | `agents/ganak.py` (Phase 2 — currently embedded in Streamlit) | Calculates topic priority — coverage gaps, exam frequency, student-performance signals. |

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
