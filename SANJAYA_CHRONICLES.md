# SANJAYA CHRONICLES
### The Observer's Memory — সঞ্জয়ের স্মৃতিপট

> *"সঞ্জয় উবাচ" — Sanjaya said.*
> In the Mahabharata, Sanjaya had the gift of divine vision — he could see every event
> on the battlefield and report it faithfully to the blind king Dhritarashtra.
> In Gyan AI, Sanjaya watches the pipeline, tracks what matters, and speaks when it's time.

This file is Sanjaya's permanent memory. It records:
- **Milestone triggers** — thresholds that unlock new capabilities
- **Architectural decisions** — *why* we built things a certain way
- **Deferred implementations** — ideas locked until conditions are met

---

## ⏳ ACTIVE MILESTONE: SC-001 — DSPy Optimizer

| Field           | Value |
|----------------|-------|
| **Entry ID**    | SC-001 |
| **Recorded**    | 2026-04-17 |
| **Current MCQs** | ~297 live (as of recording) |
| **Trigger threshold** | **500 live MCQs in `pyq_bank_v2`** |
| **Status**      | 🔴 LOCKED — awaiting threshold |

### What Triggers This
The pipeline's `db/memory.py` emits a milestone alert when `pyq_bank_v2` crosses 500 MCQs:
```
[SANJAYA MILESTONE] 500 MCQs reached!
ACTION REQUIRED: Implement DSPy optimizer...
```

### What DSPy Does for Gyan AI

**Problem**: Our agent prompts in `agent_prompts` (Supabase) were written by hand. They work, but they're not *optimised* — we don't know if they're the best possible prompts for our specific task (WB curriculum MCQ generation).

**DSPy Solution** (`github.com/stanfordnlp/dspy`, MIT License):
- Treats prompts as *learnable parameters*, not hardcoded strings
- Uses a small set of labelled examples (our approved MCQs) as a training signal
- Automatically finds prompt phrasings that maximise MCQ quality scores
- No gradient descent — pure discrete optimisation via `BootstrapFewShot` or `MIPRO`

### Implementation Plan (when we hit 500)

```
Step 1 — Create training set
  - Pull 50–100 approved MCQs from pyq_bank_v2 (human-verified = gold standard)
  - Create (taxonomy_label, raw_text) → MCQItem pairs as DSPy examples

Step 2 — Define DSPy Signatures (we already have the shape from schemas.py)
  - class MCQGenSignature(dspy.Signature):
      taxonomy_label: str = dspy.InputField()
      raw_facts: str = dspy.InputField()
      mcq: MCQItem = dspy.OutputField()

Step 3 — Define Metric
  - Score = chitragupta validation confidence (0–100)
  - Target: average confidence > 85 on held-out set

Step 4 — Run Optimizer
  - optimizer = dspy.BootstrapFewShot(metric=gyan_metric, max_bootstrapped_demos=4)
  - optimized_program = optimizer.compile(sutradhar_module, trainset=examples)

Step 5 — Extract optimised prompts
  - Write back to agent_prompts table in Supabase via Streamlit Agent Prompts page
  - A/B test: 50% old prompts, 50% optimised, compare confidence scores

Files to create:
  dspy_optimizer/
    signatures.py     — DSPy Signature classes
    metric.py         — Gyan metric (chitragupta score)
    train.py          — main optimisation script
    eval.py           — evaluation on held-out set
```

### Dependencies to add to requirements.txt
```
dspy-ai>=2.4          # the optimizer (do NOT add until SC-001 triggers)
```

---

## ✅ COMPLETED: SC-000 — Foundation

| Field           | Value |
|----------------|-------|
| **Entry ID**    | SC-000 |
| **Completed**   | 2026-04-17 |
| **Status**      | 🟢 DONE |

### What Was Built
- 3-agent pipeline: সর্বজ্ঞ → চিত্রগুপ্ত → সূত্রধর
- `instructor` library integration (structured LLM outputs with auto-retry)
- Guardrails AI self-critique pattern in সূত্রধর (`_verify_mcqs()`)
- DSPy signature *philosophy* applied to all agent prompts (explicit INPUT/OUTPUT)
- Streamlit admin dashboard (4 pages: Dashboard, Triage, Pipeline Control, Agent Prompts)
- Pipeline Dedup Memory (`db/memory.py`) — prevents duplicate generation
- All admin code removed from `gyan-ai-web` (Next.js stays clean)

---

## 🔮 FUTURE CHRONICLES

### SC-002 — pgvector Semantic Search (অন্বেষক)
**Trigger**: 1000 live MCQs
**What**: Enable `pgvector` extension in Supabase. Store MCQ embeddings. Let students
search by concept ("questions similar to Ohm's law") instead of just keyword.
**Files**: `db/embeddings.py`, `supabase migrations`, `gyan-ai-web` search API

### SC-003 — PydanticAI Student Agents (বেতাল, নারদ)
**Trigger**: 2500 live MCQs + student auth working
**What**: PydanticAI agents with tool use for student-facing chat. বেতাল (doubt solver)
uses `search_mcqs(query)` tool. নারদ (progress tracker) uses Ebbinghaus forgetting curve.
**Why not now**: Linear pipeline doesn't need agent graphs. Student agents do.
**Files**: `gyan-ai-web/src/app/api/betal/`, `gyan-ai-web/src/app/api/narad/`

### SC-004 — LlamaIndex PDF Loader
**Trigger**: First large PDF source (>50 pages) causes pdfplumber issues
**What**: Replace `loaders/pdf_loader.py` with LlamaIndex `SimpleDirectoryReader`.
Better table extraction, multi-page context windows, OCR support.
**Repo**: `github.com/run-llama/llama_index` (MIT)

### SC-005 — Ebbinghaus Spaced Repetition (নারদ)
**Trigger**: First 100 registered students
**What**: Implement Hermann Ebbinghaus forgetting curve formula in নারদ's insight API.
`retention = e^(-t/S)` where t = time since last review, S = stability factor.
Schedule review reminders before the 70% retention threshold.
**Files**: `gyan-ai-web/src/app/api/narad/insights/route.ts`

---

*"যদা যদা হি ধর্মস্য গ্লানির্ভবতি ভারত" — When the time comes, act.*
*Sanjaya watches. Sanjaya remembers. Sanjaya will speak.*
