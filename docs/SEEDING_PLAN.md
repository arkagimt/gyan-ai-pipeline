# 🌱 Pre-Pilot Data Seeding Plan

**Owner:** Arka · **Target:** ~500 MCQs across segments before 20-user pilot invites
**Status references:** see `MASTER_TODO.md` Day 5 block, `SANJAYA_CHRONICLES.md` SC-001 milestone

---

## 🎯 Coverage goal

| Segment | Slots | MCQs/slot | Subtotal | Rationale |
|---|---|---|---|---|
| School — WBBSE Class 10 | 5 subjects (Physical Sci / Life Sci / Math / Geo / Hist) | 30 | 150 | Home-market flagship; board exam year |
| School — CBSE Class 10 | 4 subjects (Sci / Math / SST / Eng) | 15 | 60 | National breadth, same age cohort |
| Entrance | JEE Main Physics/Chem/Math + NEET Bio/Chem/Phys = 6 | 15 | 90 | High-intent college-bound cohort |
| Recruitment | WBCS Prelims GS + SSC CGL Quant/Reasoning/Eng = 4 | 20 | 80 | Govt-job adult learner, high DAU potential |
| IT | AWS SAA-C03 (4 domains) + AZ-900 (4 domains) = 8 | 15 | 120 | Paid-tier beachhead; corporate buyers |
| **Total** | **27 slots** | — | **~500** | Also hits SC-001 unlock for DSPy |

**Why 500:** below this, Vaidya's eval CI has <5 items per authority, confidence intervals are meaningless. Above 500 per segment, diminishing returns until Anveshak/pgvector lands (SC-002 @ 1000).

---

## 🛠 Three seeding strategies — pick one or combine

### Strategy 1 — Manual Acharya from Streamlit admin (fastest to start)
**When to use:** today, no code changes, total control.

```
streamlit run admin/streamlit_app.py
  → "Pipeline Recommendations" panel
  → Set segment=school, limit=5, dry_run=True
  → Review the 5 priorities গণক picked
  → Untick dry_run, click "Dispatch Batch"
  → Each dispatch fires ingest_*.yml in the pipeline repo
  → Wait ~90s per run, go to /admin/triage to review+approve
```

- **Throughput:** ~3 dispatches/hr once you're reviewing concurrently. A focused weekend = 500 MCQs.
- **Failure mode:** you bottleneck on review. If you don't approve, nothing promotes to `pyq_bank_v2`.
- **Cost:** ~₹0 Groq (llama-3.1 free tier) + GH Actions minutes (free tier: 2000/mo, each run ~3 min → plenty).

### Strategy 2 — Headless CLI sweep (overnight bootstrap)
**When to use:** you want to kick off 50 dispatches and go to sleep.

```bash
# From pipeline repo root, with GITHUB_PAT + GITHUB_REPO in .env:
python -m scripts.run_acharya --limit 50 --segment school --board WBBSE --class 10 --delay 5
python -m scripts.run_acharya --limit 10 --segment entrance --delay 5
python -m scripts.run_acharya --limit 10 --segment recruitment --delay 5
python -m scripts.run_acharya --limit 15 --segment it --delay 5
```

- **Throughput:** 50 workflow dispatches in ~5 min (5s delay × 50). Each runs ~3 min on GH, but in parallel → all done in <15 min.
- **Watch for:** GitHub's 20-concurrent-runs cap. `--limit 50` fires 50 dispatches but GH will queue most. Set `--limit 15` if you want instant parallelism.
- **Still requires:** admin triage review before anything goes live.

### Strategy 3 — Nightly cron (hands-off top-up)
**When to use:** after the pilot launches and you want coverage to grow passively.

Create `.github/workflows/run_acharya_nightly.yml` (Day 4 of MASTER_TODO):
```yaml
on:
  schedule: [{ cron: '30 21 * * *' }]  # 03:00 IST
jobs:
  dispatch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11', cache: 'pip' }
      - run: pip install -r requirements.txt
      - env:
          SUPABASE_URL:          ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY:  ${{ secrets.SUPABASE_SERVICE_KEY }}
          GITHUB_PAT:            ${{ secrets.GITHUB_PAT }}
          GITHUB_REPO:           ${{ github.repository }}
        run: python -m scripts.run_acharya --limit 3 --delay 5
```

- **Throughput:** 3 MCQs-worth of dispatches per night = ~1000 MCQs/year if unreviewed. You'll still be the bottleneck on approvals.
- **Why limit=3:** keeps Groq API usage predictable, leaves headroom for manual dispatches the next day.

---

## 🚦 Recommended path for the 6-day sprint

1. **Tonight:** Strategy 2, one command:
   ```
   python -m scripts.run_acharya --limit 15 --segment school --board WBBSE --class 10 --delay 5
   ```
   Wakes up → 15 WBBSE Class 10 runs sitting in triage → review over coffee.
2. **Day 5:** Strategy 1 via Streamlit, work through entrance/recruitment/IT in parallel while reviewing. 2-hr focused session = ~30 approved MCQs.
3. **Day 6:** Wire Strategy 3 cron as part of MASTER_TODO Day 4 ops work. Now self-heals.

---

## ✅ Pre-flight checklist (do these BEFORE dispatching anything)

- [ ] `scripts/setup_health_log.sql` run in Supabase SQL editor
- [ ] `scripts/add_scope_nature.sql` run in Supabase SQL editor
- [ ] `.env` has `GITHUB_PAT` (with `repo` + `workflow` scopes) + `GITHUB_REPO=<owner>/gyan-ai-pipeline`
- [ ] GH repo secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GROQ_API_KEY`, `SARVAM_API_KEY` populated
- [ ] One smoke-test dispatch succeeded — verified `raw_data.metadata.vidushak_audit` populated in triage
- [ ] One approval-to-live cycle tested — verified `pyq_bank_v2.question_payload.metadata.source_label` populated

---

## 🔬 Quality gates (per dispatched batch)

After every 10 approvals, spot-check 2 random MCQs for:

1. **Correctness** — does the marked answer match the explanation?
2. **Provenance** — is `source_type`/`source_label` honest? (If derived from LLM knowledge, says so.)
3. **Safety** — `safety_audit.is_safe == true`; no PII, no toxicity.
4. **Bengali parity** — if `bhashacharya_audit` claims bn-IN translation, open in web `/` and confirm the Bengali renders without Unicode glyph holes.
5. **Trust chips visible** — open the MCQ in the Interactive player; confirm all four chips (confidence / source / safety / language) show.

If any fail: reject the MCQ, note the failure mode in an issue, don't scale that path.

---

## 📊 Stop conditions — when to slow down

- **If triage backlog > 100 unreviewed:** stop dispatching, catch up on reviews. Throughput is gated by you, not the pipeline.
- **If Groq 429s appear in workflow logs:** drop `--delay` to 10s. Free tier is generous but not infinite.
- **If eval CI (Vaidya weekly) drops below 80% correctness:** stop seeding, diagnose. You're injecting noise.

---

## 🪛 Fixes landed today to unblock this plan

- `ingest_competitive.yml` — authority dropdown → free-text + new `segment` input (was hardcoded to `--segment competitive`, which legacy-aliased everything to nature=recruitment → broke JEE-entrance tagging)
- `ingest_it.yml` — provider dropdown → free-text (was 6-option choice constraint; blocked Acharya from dispatching providers not in the frozen list)
- `agents/acharya.py::_priority_to_inputs` — now passes `segment` to competitive workflow so ganak's entrance/recruitment split survives the round-trip
- `scripts/run_acharya.py::_fetch_coverage` + `admin/streamlit_app.py::fetch_coverage` — now counts entrance/recruitment/IT coverage too (previously school-only; non-school segments always looked 0% → ganak mis-prioritised once any non-school content landed)

All changes compile. Ready to dispatch once the two SQL migrations run.
