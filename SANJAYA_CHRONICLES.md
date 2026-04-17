# SANJAYA CHRONICLES
### The Observer's Memory — সঞ্জয়ের স্মৃতিপট

> *"সঞ্জয় উবাচ" — Sanjaya said.*
> Sanjaya watches the pipeline, tracks milestones, and speaks when it's time.

This file records **milestone triggers** — thresholds that unlock new capabilities.
The pipeline's `db/memory.py` references this file and emits alerts when thresholds are crossed.

Detailed implementation plans and roadmap are in private documentation.

---

## Active Milestones

| ID | Threshold | Label | Trigger |
|----|-----------|-------|---------|
| SC-001 | **500 live MCQs** | DSPy Optimizer | Auto-tune agent prompts using approved MCQs as training data |
| SC-002 | 1000 live MCQs | Semantic Search | pgvector embeddings for concept-based MCQ search |
| SC-003 | 2500 live MCQs | Student Agents | AI-powered doubt solver + spaced repetition |
| SC-004 | First large PDF | PDF Upgrade | Better multi-page document processing |
| SC-005 | 100 students | Spaced Repetition | Forgetting curve-based review scheduling |

---

## Milestone Log

### SC-000 — Foundation ✅
**Completed**: 2026-04-17

3-agent pipeline (সর্বজ্ঞ → চিত্রগুপ্ত → সূত্রধর) with structured LLM outputs,
self-critique MCQ verification, Streamlit admin, and pipeline dedup memory.
