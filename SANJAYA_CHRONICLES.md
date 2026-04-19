# SANJAYA CHRONICLES
### The Observer's Memory — সঞ্জয়ের স্মৃতিপট

> *"সঞ্জয় উবাচ" — Sanjaya said.*
> Sanjaya watches the pipeline, tracks milestones, and speaks when it's time.

This file records the **complete phase roadmap** and **milestone triggers**.
The pipeline's `db/memory.py` references the milestone table below and emits
alerts when thresholds are crossed.

---

## Active Milestones (data-gated unlocks)

| ID | Threshold | Label | Trigger |
|----|-----------|-------|---------|
| SC-001 | **500 live MCQs**  | DSPy Optimizer      | Auto-tune agent prompts using approved MCQs as training data. Unlocks Phase 9. |
| SC-002 | 1000 live MCQs     | Semantic Search     | pgvector embeddings for concept-based MCQ search. Unlocks Phase 12 (Anveshak). |
| SC-003 | 2500 live MCQs     | Student Agents      | AI-powered doubt solver + spaced repetition. Unlocks Phases 14 (Betal) + 15 (Narad). |
| SC-004 | First large PDF    | PDF Upgrade         | Better multi-page document processing. |
| SC-005 | 100 students       | Spaced Repetition   | Forgetting curve-based review scheduling. |

---

## Phase Roadmap

Legend:  ✅ shipped   🔨 in-progress   ⏸ data-gated   🟡 unblocked / queued   ⚫ scope-deferred

### Core Pipeline (done)
| Phase | Name | Status | Commit / Notes |
|-------|------|--------|----------------|
| 0 | Foundation — 3-agent MVP | ✅ | Sarbagya → Chitragupta → Sutradhar |
| 1 | Instructor migration | ✅ | Pydantic-validated LLM output |
| 2 | Vidushak v1 | ✅ | Self-critique agent split out of Sutradhar |
| 3 | Sarvam-M routing | ✅ | Bengali-medium boards → Indic-native model |
| 4 | Ganak analytics | ✅ | Heuristic priority engine |
| 5 | Dharmarakshak safety gate | ✅ | Llama Guard 3 post-gen filter |
| 6 | Marker + Surya OCR | ✅ | Offline workflow, .txt siblings in Storage |
| 7 | Vidushak v2 — RAG grounding | ✅ | SOURCE_DISCONNECT check + corpus anchoring |

### Quality / Optimisation (gated or queued)
| Phase | Name | Status | Why |
|-------|------|--------|-----|
| 8  | Sutradhar v2 — few-shot exemplars  | ⏸ | Needs ≥200 golden MCQs to mine. Revisit at SC-001 threshold. |
| 9  | DSPy MIPROv2 prompt optimiser      | ⏸ | SC-001 gated — needs 500 approved MCQs as dev set. |
| 10 | Acharya — autonomous orchestrator  | ✅ | Commit `2703b2e`. Dispatches গণক priorities via GH Actions. |
| 11 | Chitragupta two-face refactor      | 🟡 | Low ROI — current split between code + Streamlit is already readable. Defer. |

### Student-Facing (mostly data-gated)
| Phase | Name | Status | Why |
|-------|------|--------|-----|
| 12 | Anveshak — pgvector semantic search | ⏸ | SC-002 @ 1000 MCQs. |
| 13 | Pragya — student quiz runtime       | ⚫ | Lives in `gyan-ai-web`, not pipeline repo. |
| 14 | Betal — doubt solver                | ⏸ | SC-003 @ 2500 MCQs. |
| 15 | Narad — FSRS-4 spaced repetition    | ⏸ | SC-003 @ 2500 MCQs + SC-005 students. |

### Scale / Ops (unblocked — no data gate)
| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 16 | Vaidya — pipeline health check   | ✅ | `agents/vaidya.py` + `scripts/run_vaidya.py`. Cron-ready. |
| 17 | Bhashacharya — language QA       | 🟡 | Vidushak already covers language_mismatch. Incremental. |
| 18 | Eval harness (Vidushak vs bank)  | ✅ | `scripts/run_eval.py`. Prereq for Phase 9. |
| 19 | RouteLLM — cost-aware routing    | 🟡 | Partial: `llm.py` already routes Bengali → Sarvam. Formalise later. |
| 20 | Ops dashboards                   | 🟡 | Streamlit Command Centre covers ~70%. Incremental. |

---

## Pending Work — picked up from current audit (2026-04-19)

1. **Phase 8/9 unlock path** — once SC-001 fires, the eval harness (Phase 18, already live)
   provides the dev set MIPROv2 needs. No new infra.
2. **Phase 11** — defer unless a concrete need emerges. Current pre-gen (agents/chitragupta.py)
   and post-gen (admin/streamlit_app.py triage) faces are understandable as-is.
3. **Phase 17 (Bhashacharya)** — only build if Vaidya's triage-rate check starts flagging
   Bengali-specific rejections.
4. **Phase 19 (RouteLLM)** — revisit when we add a third provider or cost >$50/mo.
5. **db/memory.py → agents/sanjaya.py rename** — per AGENTS.md naming rule #1. No
   behaviour change. Low priority; do when next touching memory code.

---

## Milestone Log

### SC-000 — Foundation ✅
**Completed**: 2026-04-17

3-agent pipeline (সর্বজ্ঞ → চিত্রগুপ্ত → সূত্রধর) with structured LLM outputs,
self-critique MCQ verification, Streamlit admin, and pipeline dedup memory.

### Phase 6 — Offline OCR ✅
**Completed**: 2026-04-18

Marker + Surya integrated via separate GitHub Actions workflow. Ingest path never
touches torch; OCR'd `.txt` siblings live next to PDFs in Supabase Storage.

### Phase 7 — Vidushak RAG grounding ✅
**Completed**: 2026-04-18

SOURCE_DISCONNECT added as check #7. Verifier now anchors corrections in
Sarbagya's extract when source_type ≠ llm_knowledge. Commit `e2e67a3`.

### Phase 10 — Acharya ✅
**Completed**: 2026-04-19

Autonomous batch orchestrator. Reads গণক's top-N, dispatches `ingest_*.yml`
via GitHub API. Dry-run preview + real dispatch in Command Centre.
Commit `2703b2e`.

### Phase 16 — Vaidya ✅
**Completed**: 2026-04-19

Pipeline physician. Checks Groq / Groq-Guard / Sarvam / Supabase / 24h triage-rate.
Cron-runnable via `scripts/run_vaidya.py`. Exit 0/1/2.

### Phase 18 — Eval harness ✅
**Completed**: 2026-04-19

`scripts/run_eval.py` samples N from `pyq_bank_v2`, re-runs Vidushak, reports
clean-rate + issue breakdown + per-board stratification. Prereq for Phase 9.
