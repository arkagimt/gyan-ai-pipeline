# Gyan AI — MASTER TODO
### Cross-repo action list (pipeline + web)

**Last updated:** 2026-04-25
**Related files:**
- `gyan-ai-pipeline/SANJAYA_CHRONICLES.md` — pipeline phase roadmap
- `gyan-ai-web/UI_OVERHAUL_TODO.md` — UI phase roadmap
- `gyan-ai-pipeline/AGENTS.md` — agent registry
- `gyan-ai-pipeline/SCOPE_DECISIONS.md` — board/exam inclusion decisions

**Source of truth:** this file aggregates both repos' outstanding work + the MVP launch sequencing. When something is shipped, tick the box **here first**, then in the repo-local file.

---

## 🔴 Status snapshot (2026-04-20)

### Shipped across both repos
- Pipeline: all 9 active agents + Sanjaya chronicler (Sarbagya, Chitragupta, Sutradhar, Vidushak, Dharmarakshak, Bhashacharya, Ganak, Acharya, Vaidya).
- Pipeline: `ENTRANCE_TREE` / `RECRUITMENT_TREE` split in `curriculum.py`; `Segment` enum extended.
- Pipeline: `llm.py` pluggable Provider registry (Phase 19).
- Pipeline: `scripts/run_eval.py`, `run_vaidya.py`, `run_acharya.py`, `setup_health_log.sql`.
- Pipeline: `SCOPE_DECISIONS.md`.
- Web: Entrance + Recruitment tabs on `/competitive/page.tsx`.
- Web: PreferencesContext (lite mode, dark mode, theme override).
- Web: ThemePicker with hover preview in `/profile`.
- Web: Continue-where-you-left-off card.
- Web: TTS button + language detection in `InteractiveMCQ`.
- Web: Trust chips row + modal explainers in `InteractiveMCQ` (front-end only — see **Day 1 fixes**).
- Web: Age-adaptive mastery dashboard in `/profile`.
- Web: `/about` with "No ads, ever" pledge.
- Web: UGC flag button + `question_flags` table + 5-reason modal.
- Web: Print-set button + `@media print` stylesheet.
- Web: `lighthouserc.js` + `performance-budget.json` + README §Performance Budget.
- Web: IT blueprint bars + coverage tracker.
- Web: Bodhibriksha3D defer-load + couplets.
- Web: `public/manifest.json` + icons + content provenance display.

### Critical gaps found in 2026-04-20 audit (fix before users)
1. 🔴 **Metadata round-trip is broken** — `db/supabase_loader.py` drops `vidushak_audit / safety_audit / bhashacharya_audit / source_type` when pushing to Supabase. Web reads them back → chips render empty.
2. 🔴 **Scope/nature not persisted** — fields exist on `TaxonomySlice`, never populated, never written, no DB column.
3. 🟠 **PWA middleware not registered** — `manifest.json` + icons exist, but `next.config.ts` has no service-worker registration. "Installable PWA" is cosmetic.
4. 🟠 **DPDPA parental consent missing** — signup allows minors without consent. Legal blocker.
5. 🟠 **No admin triage for `question_flags`** — students flag into the void.
6. 🟡 **Stale "competitive" hardcodes** in Acharya/Ganak/CLI — autonomous ingest can't file into Entrance vs Recruitment yet.

---

## 🎯 Day 1 — Core plumbing fixes (ship today)

### Pipeline (`gyan-ai-pipeline/`)
- [x] Fix metadata round-trip in `db/supabase_loader.py` — forward `vidushak_audit`, `safety_audit`, `bhashacharya_audit`, `source_type`, `source_label`, `edit_log` (empty scaffold), `last_reviewed_at` (null scaffold) into `raw_data`.
- [x] Add `derive_scope_nature(taxonomy)` helper in `models/schemas.py` and auto-fill on `TaxonomySlice` build (gyan_pipeline.py + ganak.taxonomy_slice).
- [x] Write `scope` + `nature` to triage entries (top-level columns + mirror into `raw_data` for triage UI).
- [x] Add `scripts/add_scope_nature.sql` migration (ALTER TABLE + indexes).
- [x] Expand CLI `--segment` choices to include `entrance` + `recruitment` (gyan_pipeline.py, scripts/run_acharya.py, admin/streamlit_app.py).
- [x] Update `ganak.analyze` to iterate `ENTRANCE_TREE` + `RECRUITMENT_TREE` separately with proper segment tags.
- [x] Update `acharya._WORKFLOW_BY_SEGMENT` + helpers to route entrance/recruitment (both point to `ingest_competitive.yml` until we split workflows).
- [x] Smoke-test: `python -m py_compile` on every touched file.

### Web (`gyan-ai-web/`) — no Day 1 work
Day 1 web-side claims in UI_OVERHAUL_TODO (print CSS, README perf section) were already shipped — audit was stale.

---

## 🎯 Day 1.5 — Seeding-sprint unblockers (landed 2026-04-21)

Fixes so the Day 5 seeding sprint can actually run. Triggered by audit of existing workflow YAMLs + coverage fetchers.

- [x] `ingest_competitive.yml` — authority `type: choice`→`type: string` (was 4-WB-option dropdown; blocked UPSC/JEE/SSC dispatches via API).
- [x] `ingest_competitive.yml` — new `segment` input forwarded to `gyan_pipeline.py --segment` (was hardcoded `competitive`, which legacy-aliased JEE-entrance to `nature=recruitment`).
- [x] `ingest_it.yml` — provider `type: choice`→`type: string` (same over-constraint trap).
- [x] `agents/acharya.py::_priority_to_inputs` — forwards `segment` so ganak's entrance/recruitment split survives into the workflow call.
- [x] `scripts/run_acharya.py::_fetch_coverage` + `admin/streamlit_app.py::fetch_coverage` — multi-segment aware; entrance/recruitment/IT no longer look 0%-covered by default.
- [x] `sparse-halo/SEEDING_PLAN.md` — 3-strategy operator playbook (manual Streamlit / CLI sweep / nightly cron) + pre-flight SQL checklist + per-batch quality gates.

## 🎯 Day 1.75 — Official source registry (landed 2026-04-21)

Triggered by legitimate Q: "can we just buy PW?" Answer: no, but there's structured work to kill the excuse. Goal is a tier-flagged registry of legally-reusable sources per segment, plus a bootstrap script that ingests them end-to-end with strong provenance tagging.

- [x] `gyan-ai-pipeline/sources/OFFICIAL_SOURCES.md` — URL registry with tier flags per row (🥇 gold / 🥈 silver / 🥉 bronze / 🟥 gap / 🏆 IT-vendor-gold) covering CBSE + ICSE + WBBSE + WBCHSE + NCERT + UPSC + JEE + NEET + SSC + GATE + AWS + Azure + GCP + Cisco.
- [x] `gyan-ai-pipeline/sources/GAP_SOURCING.md` — action items for tier-bronze/gap rows (CISCE Publications orders, WBBSE/WBCHSE/WBPSC Bhawan visits, 4-teacher outreach checklist, RTI template) + formal **Dumps Policy** section banning ExamTopics/PW-style sources.
- [x] Added `SourceType` enum to `models/schemas.py` — 8 tiers (`official_past | official_sample | ncert_exemplar | board_publication | vendor_docs | vendor_sample | teacher_upload | llm_knowledge`) with per-tier docstrings explaining Trust Chip mapping.
- [x] `db/supabase_loader.py::_FORWARDED_METADATA_KEYS` — now forwards `provenance_tier` + `source_url` into `raw_data.metadata.*` so web Trust Chip can render the right badge.
- [x] `scripts/bootstrap_official_corpus.py` — registry-driven orchestrator (download → dispatch `ingest_*.yml` → stamp provenance). Dry-run verified on UPSC / NCERT / AWS / JEE rows. 10 starter rows covering all 4 segments.
- [x] **Explicit no-dumps policy** documented in `GAP_SOURCING.md` §"Dumps Policy" as first-class rule. Code-review rule: new data source = row in OFFICIAL_SOURCES.md or GAP_SOURCING.md, or PR rejected.

**Next step after these (Arka):** run one real `bootstrap_official_corpus.py --only upsc --limit 1` (no dry-run) to confirm the download→dispatch→triage chain works end-to-end on UPSC — lowest-risk row, rock-solid free-legal source.

---

## 🎯 Day 2 — PWA (real, not cosmetic) ✅

Hand-rolled (no next-pwa / no Workbox dep). All wiring in place; `tsc --noEmit` clean.

- [x] Hand-roll vanilla Service Worker — `gyan-ai-web/public/sw.js` (shell precache + cache-first static + network-first HTML + version bump on deploy).
- [x] Register service worker via client component — `src/components/ServiceWorkerRegistrar.tsx` (mounted from `AppProviders`; production-only, silent on failure, load-event registration so SW install does not fight initial-route JS on 3G).
- [x] `src/lib/offlineCache.ts` → IndexedDB chapter cache (`gyan-offline` DB, `chapters` store, SSR-safe). Public API: `saveChapterContent`, `getChapterContent`, `hasChapterContent`, `listCachedChapters`, `removeChapterContent`, `estimateOfflineSizeKB`.
- [x] "📥 Download for offline" button — `src/components/OfflineDownloadButton.tsx` — wired into `ContentPanel` PYQ view (next to Print Set) and Notes view.
- [x] 🟢 "Available offline" badge — same component toggles to green pill when cached; click again to remove.
- [x] Install prompt after 3rd session — already shipped as `InstallPrompt.tsx` (discovered during Day 2 scope check; no rework needed).

**Not-done-by-design:**
- `next-pwa` skipped — the plugin drags in Workbox (+150 kB) and obscures the SW we want to own. Vanilla is 170 lines, inspectable, versionable.
- Chapter downloads live in IDB, **not** Cache Storage, because we need enumeration for the future `/settings/offline` page.

**Smoke-tested on dev laptop 2026-04-21:** SW registered, two gyan-* caches present, IDB round-trip (save → refresh → remove) clean, offline mode renders cached chapter.

---

## 🎯 Day 2.5 — Opus provider registered, call-sites OFF (pre-investment posture) ✅

**Decision 2026-04-21:** Opus stays wired as a provider but no agent calls it until investment. For the 100-user pilot we use the free-tier stack (Groq/Llama + Sarvam) and Gemini-via-AI-Studio for founder-reviewed seed content. Saves ~$120 per 2,000-MCQ batch.

- [x] `config.py` — `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL` env-readable (no cost if key is absent).
- [x] `llm.py` — `_make_anthropic_client()` factory + `register_provider("anthropic", ...)` with empty `supports_languages` (opt-in-only; can't be selected accidentally).
- [x] `requirements.txt` — `anthropic>=0.34` listed. Safe to install; no API calls happen without the env key + a `model_hint` call-site.
- [x] `agents/sutradhar.py` — Opus opt-in **reverted**. Comment left at the call site documenting the one-line flip when budget allows.
- [x] `agents/vidushak.py` — Opus opt-in **reverted** on both audit + repair. Same guidance comment left in place.
- [x] Static verification — all files parse cleanly; no live `model_hint="anthropic"` refs remain.

**Post-investment flip:** Three one-liners to re-enable — add `model_hint="anthropic"` to Sutradhar-en generation, Vidushak audit, and Vidushak repair-non-Bengali. No refactor needed.

---

## 🎯 Day 3 — Legal + compliance
- [ ] DPDPA-2023 parental consent flow — `Auth.tsx` signup branches by `class_num` age-derivation; parent-email OTP; `parental_consent_at` timestamp.
- [ ] Privacy policy page update.
- [ ] Kick off legal review (external counsel, 2-week lead time — start now so it resolves by user test).

## 🎯 Day 4 — Ops + content triage
- [ ] Admin triage tab for `question_flags` (extend `admin/streamlit_app.py` — reuse existing triage pattern).
- [ ] GitHub Actions `run_acharya_nightly.yml` — `cron: '30 21 * * *'` (03:00 IST) — `python -m scripts.run_acharya --limit 3 --delay 5`.
- [ ] GitHub Actions `run_vaidya_weekly.yml` — Sunday 02:30 UTC (08:00 IST) — posts to Telegram/Discord webhook on fail_count > 0.
- [ ] Eval CI gate — `scripts/run_eval.py --limit 30` on every `main` push; fail CI if clean-rate < 80%.
- [ ] Run `scripts/setup_health_log.sql` + `scripts/add_scope_nature.sql` in Supabase (user action). ⚠️ `add_scope_nature.sql` (web version `migration_scope_nature.sql`) was run 2026-04-19. Pipeline version is idempotent, safe to re-run. `setup_health_log.sql` still pending.

## 🎯 Day 5 — Seed real content (🧑‍💼 **Arka-owned**)

> **Arka's task, not mine.** Claude can help write dispatch scripts and
> analyse what's missing, but the actual green-button clicks + content quality
> review belong with the founder until a teacher partner is onboarded.
>
> **📖 Full operator playbook: [`SEEDING_PLAN.md`](./SEEDING_PLAN.md)** — three
> strategies (manual Acharya / CLI sweep / nightly cron), pre-flight checklist,
> per-batch quality gates, stop conditions.

- [ ] 🧑‍💼 **Decide the data-feeding strategy for pilot** (Arka is scoping this):
  - Manual Acharya dispatches from Command Centre (safe, slow, one-click)?
  - Acharya nightly cron (hands-off, needs Day 4 #2 to land first)?
  - Teacher upload (needs Phase 6.2 MVP, ~3 days to build)?
  - External PDF corpus ingest via `ocr_textbook.yml` → `ingest_school.yml` chain?
  - Hybrid: teachers seed PYQs, Acharya fills syllabus gaps around them.
- [ ] 🧑‍💼 **Seed coverage targets before pilot invites** — minimum viable stock:
  - **School (WB-first):** WBBSE Class 10 — Physical Science, Mathematics, Life Science, Geography, History (≥30 MCQs per subject ≈ 150 MCQs).
  - **School (national):** CBSE Class 10 — Science, Mathematics, SSt (≥20 MCQs per subject ≈ 60 MCQs).
  - **Entrance:** JEE Main + NEET UG — top 3 topics each (≥15 MCQs per topic ≈ 90 MCQs).
  - **Recruitment:** WBCS Prelims + SSC CGL — top 2 topics each (≥20 MCQs per topic ≈ 80 MCQs).
  - **IT:** AWS SAA-C03 + AZ-900 — every domain (≥10 MCQs per domain ≈ 120 MCQs).
  - **Total target: ~500 MCQs** — also hits **SC-001** milestone which unlocks DSPy Phase 9.
- [ ] 🧑‍💼 Manually review 20 random MCQs in `/admin/triage` per dispatched batch — catch systemic issues before they scale.
- [x] Run Lighthouse on home + `/school` dashboard; fix top 2 offenders. ✅ 2026-04-25: All 4 URLs pass all budgets (Perf 96–98, A11y 95–100, LCP ≤1305ms, TBT ≤38ms, CLS ≤0.007). Config fixed (budgetsFile conflict removed).
- [ ] Smoke-test trust chips visibly populated on 10 random MCQs (regression check on Day 1 fix).
- [ ] Claude assists: analyse coverage gaps per Vaidya / Ganak report; suggest next 5 dispatches.

## 🎯 Day 6–7 — Pilot launch
- [ ] Invite 20 pilot users from Arka's network + 2 WB teacher contacts (Phase 6.2 seed).
- [ ] Observe behaviour: bounce rate, first-question time, TTS usage, flag submissions.
- [ ] Fix top 3 surfaced issues same day.
- [ ] Expand to 100 users once stable.

---

## 🛠 Post-sprint (100 → 1000 users)

### Content moat
- [ ] Teacher PYQ upload (`/admin/teacher-upload`) — Phase 6.2.
- [ ] UGC triage flow for `question_flags` (was Day 4, deepen here).
- [x] Tag every IT MCQ to an `itBlueprints` domain — makes coverage bars truthful. ✅ 2026-04-25: Domain filter `<select>` in ContentPanel + ITBlueprintBars reads from `assessment_logs` (fuzzy topic→domain match, falls back to localStorage).
- [ ] WhatsApp weekly report for parents (`/api/reports/weekly`).

### UX depth
- [ ] Multi-user PIN switcher (family device) — Phase 4.7 in UI_OVERHAUL_TODO.
- [ ] Subject-first secondary navigation — Phase 4.5 (currently deferred — revisit after picking SchoolDashboard vs Sidebar as the source-of-truth nav).
- [ ] Age-adaptive dashboard variants (kids / middle / board-year / adult).
- [ ] a11y audit (WCAG AA): `aria-label` sweep, focus rings, contrast on per-state themes, NVDA pass.

### Scale ops
- [ ] Move secrets to GitHub OIDC (kill long-lived PATs).
- [ ] Supabase connection pool sizing once 1000+ students.
- [ ] Rate-limit `question_flags` insert RLS.

### Cross-segment question overlap — Phase 1.4 case study
- [ ] Design doc: question fingerprinting strategy (exact / topic / semantic).
- [ ] Precompute cross-reference table: NCERT ↔ UPSC / JEE / NEET / GATE / SSC / TET.
- [ ] Badge surface: quiz results + question card.
- [ ] Implement after SC-002 (pgvector at 1000 MCQs).

---

## 🔭 Long-term / data-gated (SC thresholds from Sanjaya)

| Milestone | Threshold | Unlocks |
|-----------|-----------|---------|
| SC-001 | 500 live MCQs | Phase 9 — DSPy MIPROv2 prompt optimiser (eval harness Phase 18 already live) |
| SC-002 | 1000 live MCQs | Phase 12 — Anveshak (pgvector semantic search) |
| SC-003 | 2500 live MCQs | Phase 14 Betal (doubt solver) + Phase 15 Narad (FSRS-4 spaced repetition) |
| SC-004 | First large PDF | PDF processing upgrade |
| SC-005 | 100 students | Spaced repetition activation (post-Narad) |

---

## 🪔 Investor demo pre-flight (run through right before the pitch)

- [ ] `/about` shows live counts: "Questions verified: N · Questions rejected: M · Active agents: 9" — wire to Supabase.
- [ ] Vaidya green-health screenshot (recent 10-run emoji strip).
- [ ] Trust chips populated on every demoed MCQ.
- [ ] Acharya nightly cron showing N workflows dispatched in last 7 days.
- [ ] One teacher testimonial OR one student testimonial (1-minute video).
- [ ] Lighthouse mobile score ≥ 90 on landing + one content page.
- [ ] `/admin/triage` walkthrough shows flag-volume + review-lag metrics.
- [ ] DPDPA consent flow demoed in signup.

---

## 📜 Rules of engagement

1. **Every new file change** → update the relevant repo-local file (`UI_OVERHAUL_TODO.md` / `SANJAYA_CHRONICLES.md`) AND tick this file.
2. **Never add features** before the Day 1–4 critical fixes land. Feature debt compounds faster than content debt.
3. **Data feed pause** — do NOT run Acharya at scale until Day 1 metadata fix is verified on 3 triage entries. Otherwise we spend tokens generating audit-blank MCQs.
4. **When this file conflicts with a repo-local file, this file wins.** Edit the other file to match.
