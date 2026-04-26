# Gyan AI — MASTER TODO
### Cross-repo action list (pipeline + web)

**Last updated:** 2026-04-25
**Related files:**
- `gyan-ai-pipeline/SANJAYA_CHRONICLES.md` — pipeline phase roadmap
- `gyan-ai-web/UI_OVERHAUL_TODO.md` — UI phase roadmap (now subordinate to this file's Wave Program)
- `gyan-ai-pipeline/AGENTS.md` — agent registry
- `gyan-ai-pipeline/SCOPE_DECISIONS.md` — board/exam inclusion decisions

**Source of truth:** this file aggregates both repos' outstanding work + the MVP launch sequencing. When something is shipped, tick the box **here first**, then in the repo-local file.

---

## 🌟 2026-04-25 Wave Program — UI redesign + ExamMode + a11y

Sequenced rollout consolidating: PearsonVue-style MCQ player, light/dark theme redesign,
Streamlit polish, and the WCAG a11y backlog. Each wave is ONE coherent commit.

### Wave 2.5 — Hotfix sweep (post-Wave-2 user QA findings, 2026-04-25 evening)
- [x] **Palette congestion**: dropped `xl:grid-cols-10` in `QuestionPalette.tsx`,
  bumped gap to 2, used aspect-square + min-w-40px tiles, widened aside in
  `ExamModePlayer.tsx` from 240→300px. 5 × 20 grid renders comfortably now.
- [x] **Removed "SCHOOL SECTION" header** from `Sidebar.tsx`.
- [x] **Added back/exit chip to Quantum Lab** — floating "← Exit Quantum" top-left,
  uses router.back() with /profile fallback.
- [x] **Removed dead "Talk to Sarbajna" link** from CommandPalette. Real chat panel
  is queued as Wave 8 below.
- [x] **Removed "Activate Quantum Theme" command** from CommandPalette + the
  toggleTheme handler + the quantumActive state. Topbar Sun/Moon is the single
  source of truth for dark/light.
- [x] **Bodhi tree load**: decision = keep the 500ms-min CSS fallback. Intentional
  `requestIdleCallback` defer until browser idle. No code change.

### Wave 2.8 — AWS exam code refresh (2026-04-25 late)

AWS rotated two cert programs in the last 7 months:
  - SOA-C02 (SysOps Administrator) RETIRED 2025-09-29 → SOA-C03 (CloudOps Engineer Associate)
  - MLS-C01 (ML Specialty) RETIRING 2026-03-31 → split into MLA-C01 (ML Engineer
    Associate) + AIF-C01 (AI Practitioner — new foundational cert)

Slugs migrated (no Supabase content existed for these → safe rename, no DB
migration required):
  - aws-sysops  → aws-cloudops
  - aws-mls     → aws-mla
  - NEW         + aws-aif

Files touched:
- [x] `gyan-ai-web/src/lib/taxonomy.ts` — exam name + topics blueprint
- [x] `gyan-ai-web/src/components/ITDashboard.tsx` — EXAM_SLUG_MAP entries
- [x] `gyan-ai-web/src/lib/types.ts` — SLUG_LABEL_MAP entries
- [x] `gyan-ai-web/src/data/staticITDataExtended.ts` — renamed key + IDs (n-aws-mls-* → n-aws-mla-*, ep-aws-mls-* → ep-aws-mla-*)
- [x] `gyan-ai-web/scripts/seed_it_data.mjs` — DB seed script
- [x] `gyan-ai-pipeline/tests/test_loader_slug.py` — canonical slug whitelist
- [x] `gyan-ai-pipeline/scripts/audit_it_slugs.sql` — header + new Q6 to detect
  any orphan rows still using retired slugs (returns 0 unless someone loaded
  content under the old slugs out-of-band)

Verification: ran AST-based whitelist check — 28 slugs, all valid kebab-case,
new slugs present, retired slugs absent. ✅

### Wave 2.7 — Wildcard CSS + IT-respects-light/dark + SW cache bump (2026-04-25 late)

User reported persisting glass/ghost in 3 spots after Wave 2.6:
  1. Home page primary lens card (`bg-white/55` slipped through enumerated /20-/90 list)
  2. Competitive Narad Recommends bar (`bg-red-50` for high-urgency, not covered by /X overrides)
  3. IT segment in light mode showed cyberpunk dark gradient over light page bg → "ghostly gray"

Fixes:
- [x] **Wildcard CSS** in `globals.css` — replaced enumerated `.bg-white\/20...90` /
  `.border-white\/40...70` rules with attribute selectors `[class*="bg-white/"]` and
  `[class*="border-white/"]`. Catches ALL opacity values incl. arbitrary brackets
  (`bg-white/[0.04]`, `bg-white/55`, `bg-white/[0.06]` etc.) in one rule.
- [x] **IT light-mode tokens** — added `[data-dark="false"][data-theme="aws|azure|...|"]`
  blocks that override `--theme-bg/card/text/muted/border` to light parchment values
  while KEEPING segment accent + highlight (AWS orange, Azure blue, etc. still pop).
  IT segments now respect light/dark mode preference like every other segment.
- [x] **NaradInsights refactor** — dropped 60+ `segment === 'it'` branches in favour
  of `useCyberpunk = isDark` (from PreferencesContext). The cyberpunk dark gradient
  now applies in dark mode for ANY segment; light mode + ANY segment uses the
  white-card style (which the wildcard CSS keeps from looking ghostly on dark too).
  Also renamed ReadinessGauge prop `segment` → `dark: boolean`.

PWA service worker:
- [x] **CACHE_VERSION bumped** from `gyan-v1-2026-04-21` → `gyan-v2-2026-04-25`. This
  was stale across multiple deploys (Wave 2 / 2.5 / 2.6). Without the bump the SW
  fingerprint stays identical and browsers serve cached old shell — students who
  installed the PWA before today were not seeing my fixes. Comment in sw.js now
  flags this as required workflow.
- [x] **Wave 9: automate CACHE_VERSION bump (2026-04-26)** — shipped.
  `gyan-ai-web/scripts/inject-sw-version.mjs` rewrites the CACHE_VERSION
  line on every `next build` via package.json `prebuild` script.
  Format: `gyan-<git-sha-7>-<YYYYMMDD>` (falls back to timestamp when git
  isn't available). Idempotent — no write when already current. Manual
  invocation: `npm run sw:version`. Vercel deploys auto-trigger via
  `next build`. Eliminates the manual-bump-forgotten bug that bit Waves
  2.5/2.6/2.7.

### Wave 2.6 — Sync audit fixes + matte panel + school sidebar (2026-04-25 night)
Triggered by user QA round 2 — comprehensive audit of profile tabs, command
palette, settings sync, and dark theme aesthetics.

Audit findings (FULLY WORKING):
- Profile tabs (Overview / Settings / Security): all 3 wired correctly
- Profile dropdown shortcuts: all 3 call setActiveTab properly
- CommandPalette items: Open Quantum Labs, My Progress, all search items
  (dispatch GYAN_NAV → PlatformContext listens at line 171, calls router.push)
- Topbar: Search, SegmentSwitcher, RegionSwitcher, Bell, Lite mode, Dark mode
- View Learning Analytics toggle (CompetitiveDashboard / ITDashboard)
- NaradInsights tab switcher (Exam Readiness / Velocity / Spaced / Cross)

Audit findings (REAL BUGS — fixed):
- [x] **Narad Recommends arrow** — `setExpanded` toggle with no panel attached.
  Arrow rotated 90° but nothing else happened. Removed expanded state, made
  the button a real CTA → router.push to segment dashboard.
- [x] **Exam Readiness cards** (Class 10 Boards, Vidyasagar Science Olympiad,
  etc.) — `<motion.div>` had no onClick. Now `<motion.button>` with
  navTargetForProvider() routing to /school | /competitive | /it based on
  exam.provider lookup. Added focus-visible ring + aria-label.
- [x] **School Sidebar empty space** in dashboard view — Sidebar was always
  rendered, taking left column even when no activePath (dashboard view has
  no tree to drill). Now gated on activePath: dashboard view = no sidebar
  (full-width content), drilled view = sidebar with nav tree. Particularly
  ugly in dark mode.

Style decision (locked):
- [x] **Matte panel for non-IT in dark mode** — IT section's solid dark-card
  aesthetic is preferred over the glassmorphic / frosted-glass look that
  school+competitive currently render in dark mode. Components hardcoded
  bg-white/X + backdrop-blur-Y instead of theme tokens, so the dark-mode
  token system was bypassed. Added a CSS-side override block in globals.css
  that **only** activates when data-dark="true": disables backdrop-filter,
  remaps bg-white/X → var(--theme-card), border-white/X → var(--theme-border),
  text-charcoal → var(--theme-text). Light mode UNTOUCHED — glassmorphic
  stays for light themes which it suits. IT segments unaffected (already
  matte). Trade-off acknowledged: !important is required because Tailwind
  utilities are specificity-equivalent. This is the least-bad way to land
  the look fix without a 30-file component sweep.

Audit findings (NOT bugs, roadmapped):
- Sarbagya chat → Wave 8 (already in TODO)
- Cross-segment foundation recommendations → Wave 7 Part B

### Wave 2 — ExamModePlayer (UNIVERSAL across school + competitive + IT)
- [x] `gyan-ai-web/src/components/exam/ExamModePlayer.tsx` — PearsonVue-style player with
  intro / in-progress / submitted phases, age-adaptive defaults, localStorage resume,
  keyboard nav (← → F S), aria-labels everywhere, focus-visible rings.
- [x] `gyan-ai-web/src/components/exam/QuestionPalette.tsx` — accessible 10×N grid,
  color-coded (answered / unanswered / flagged / correct / wrong).
- [x] `gyan-ai-web/src/components/exam/ExamResultsScreen.tsx` — score hero, count tiles,
  per-domain breakdown (IT only), review-all CTA.
- [x] `gyan-ai-web/src/components/ContentPanel.tsx` — replaces `<PYQCards>` (kept as
  print-only fallback). Domain-by-idx mapping passed for IT per-domain results.
- [x] Age-adaptive defaults baked in:
  - IT certs / competitive       → exam mode, 60min, batch 100
  - School class 9-12             → exam mode, 60min, batch 50
  - School class 6-8              → review mode, no timer, batch 20
  - School class 1-5              → review mode, no timer, batch 10
- [x] TSC clean, ESLint clean on touched files (project-wide pre-existing lint debt unrelated)

### Wave 3 — Light/dark theme redesign (NON-IT only)
*Locked direction:* "Bengali Manuscript Warmth" — parchment + indigo + saffron + teal,
Cormorant Garamond display + Inter Tight body. IT's `data-theme="aws|azure|...|"`
dark cyberpunk untouched.
- [ ] Update `gyan-ai-web/src/app/globals.css` `:root` and `[data-theme="school"]` palettes
- [ ] Add font imports (Cormorant Garamond + Inter Tight) via Next.js `app/layout.tsx`
- [ ] Replace 20 raw `text-gray-*` / `text-slate-*` usages with `text-text-muted` token
- [ ] Replace `bg-white/30`, `text-charcoal` hardcodes in school/competitive pages
- [ ] Fix `competitive/page.tsx:87` tab dark-mode regression
- [ ] Sanity-check IT pages still render their own dark theme correctly

### Wave 11 — Admin QA fixes (2026-04-26 evening)

User QA round on Streamlit admin surfaced 4 issues. All addressed:

1. **PDF upload "42P10" — ON CONFLICT mismatch** (Textbooks page)
   `curriculum_sources` table missing UNIQUE constraint on
   `(board,class_num,subject)` and `(board,class_num,subject,chapter)` that
   the upsert calls in admin/streamlit_app.py:1450 require.
   - [x] `scripts/fix_2026_04_26_admin_bugs.sql` adds two PARTIAL unique
     indexes (one for chapter-NULL rows, one for chapter-present rows).
     Postgres ON CONFLICT inference matches partial unique indexes (9.5+),
     so both upsert shapes resolve correctly.

2. **Vaidya health check "42703" — column does not exist**
   `agents/vaidya.py:180` queries `ingestion_triage_queue.rejection_reason`
   but the column was never added to the live schema. Same column is used
   by chitragupta + schemas.TriageRow.
   - [x] SQL adds `rejection_reason TEXT` (nullable) + a partial index
     for the common `WHERE status='rejected' ORDER BY reviewed_at` query.

3. **Coverage Map missing "Global IT" scope at top**
   The page jumped to school-board radio (WBBSE/WBCHSE/CBSE/ICSE), with
   Global IT section scrolled below. Curators couldn't find IT coverage
   at a glance.
   - [x] `admin/streamlit_app.py:page_coverage_map` now starts with a
     scope selector (📚 School Boards / 🌍 Global IT / 🏛️ Competitive).
     IT view jumps straight to the per-provider drill-down. Competitive
     scope shows a "queued as Wave 10" placeholder.
   - [x] Extracted IT rendering into `_render_it_coverage()` helper so the
     top-of-page IT scope and the bottom-of-school-scope appendix share
     the same code.

4. **Global IT coverage showing 0 MCQs** despite 5 Microsoft seeds loaded
   Two layers: (a) Streamlit Cloud hadn't redeployed since Wave 4 IT_TREE
   alignment (still showing verbose names "AZ-900 Azure Fundamentals"),
   (b) existing pyq_bank_v2 rows have per-batch topic from before Wave 4.5.
   - [ ] **Manual: Streamlit Cloud auto-deploys from main branch within
     ~5 min of push** — verify on next visit.
   - [ ] **Manual: run** `python scripts/backfill_topic_per_mcq.py
     --segment it --commit` once SUPABASE_URL + SERVICE_KEY are in env.
     Updates 500 existing rows so Coverage Map shows 11/11 not 4/11.

5. **GROQ_API_KEY missing in Vaidya output** — env config issue, not code.
   - [ ] **Manual: add `GROQ_API_KEY` to Streamlit Cloud Secrets** so the
     `groq` + `groq_guard` health checks pass on next run.

6. **Defensive: DB-level CHECK constraint on metadata.exam slug shape**
   - [x] SQL adds `CHECK (metadata->>'exam' ~ '^[a-z0-9]+(-[a-z0-9]+)*$')`
     on pyq_bank_v2 + study_materials. Belt-and-braces against future
     direct INSERTs bypassing the loader's lowercase-kebab guard.

### Wave 4.5 — Per-MCQ topic taxonomy in loader (2026-04-26)

Closes the IT_TREE coverage gap noted as a known limitation in Wave 4.

Root cause: `db/supabase_loader.py:_build_pyq_entry` set `raw_data["topic"]`
from `taxonomy.topic` (constant across an entire StudyPackage). With 25-MCQ
batched packages, only 1 unique topic value persisted per batch — admin
Streamlit's IT coverage map showed ~4/N distinct topics for a 100-MCQ exam.

Fix:
- [x] `db/supabase_loader.py` — `effective_topic = mcq.topic_tag if mcq.topic_tag else taxonomy.topic`
  preserves backward-compat for legacy callers without topic_tag, but
  every LLM-knowledge seed populates topic_tag (extracted in Wave 4 audit
  for AZ-900: 11 distinct, AI-900: 11, DP-900: 11, AZ-104: 16, DP-600: 10).
  All future seeds + DP-700 will get full topic distribution.
- [x] `scripts/backfill_topic_per_mcq.py` — one-shot migration to fix the
  5 already-loaded Microsoft seeds. Reads each row's `topic_tag` field
  (untouched, per-MCQ from the seed JSON) and writes it back into
  `question_payload.topic`. Idempotent + dry-run safe.
  Usage: `python scripts/backfill_topic_per_mcq.py --segment it --commit`
  (currently NOT auto-run — manual when Arka decides).

After backfill is run, admin Coverage Map should show full 11/11 topics
covered for AZ-900, etc., instead of ~4/11.

### Wave 4 — Streamlit polish (capped by framework)
- [ ] `admin/.streamlit/config.toml` — brand colours (saffron primary, teal secondary)
- [ ] Tighten 4-5 `st.markdown` blocks for visual consistency
- [ ] Prune confusing nested expanders in Coverage Map
- [ ] **Fix IT_TREE key mismatch** — `curriculum.py` uses verbose names ("AZ-900 Azure
  Fundamentals", "Cloud Concepts"); DB writes short slugs. Either normalise IT_TREE keys
  to match DB or add a key-alias mapping in `_bump_coverage`. **This is why Global IT
  shows 0% in Command Centre / Coverage Map despite my 2026-04-25 widget commit.**

### Wave 5 — P0 a11y + bugfix sweep
- [ ] Add `aria-label` to all 86 unlabelled `<button>` elements (WCAG 2.1 AA blocker)
- [ ] Add `focus-visible:` ring styles project-wide (WCAG 2.4.7 blocker)
- [ ] De-duplicate school sidebar vs SchoolDashboard tree on PC view (Observation 1)
- [ ] Replace remaining `text-charcoal/30`, `bg-saffron/15`, etc hardcodes with theme tokens

### Wave 7 Part B — Cross-segment foundation recommendations (2026-04-26)

Completes the "lens not walls" arc. Wave 7 Part A delivered the navigation
affordance (Topbar SegmentSwitcher + home primary-lens highlight + Profile
copy reframe). Part B adds the *content recommendation* — small cards that
say "📚 Build foundation: <relevant school content>" and route the student
directly to that path.

Shipped:
- [x] `gyan-ai-web/src/components/CrossSegmentFoundation.tsx` — exam-aware
  recommendation card. Per-exam mapping covers UPSC family (NCERT 6-12
  Polity/History/Geography/Economy), entrance exams (JEE/NEET/GATE/CAT all
  pointing to NCERT 11-12), SSC/Railway/WB Police (WBBSE 8-10 maths +
  English), bank PO (RBI/SEBI/IBPS PO mapped to economics + commerce). Falls
  through to a generic encouragement card when no exam picked yet.
  Theme-aware (parchment + tone-coloured ring), focus-visible, aria-labels.
- [x] `gyan-ai-web/src/components/CompetitiveDashboard.tsx` — wires
  `<CrossSegmentFoundation examId={activeExamId} onNavigate={onNavigate} />`
  between BetalCTA and the main wizard grid. Re-renders as the wizard
  selects different exams.
- [x] `gyan-ai-web/src/app/(platform)/school/page.tsx` — discreet "Building
  foundation for competitive prep / your IT certifications" banner that
  appears when a non-school-primary user visits /school. Reassures: "Your
  competitive/IT recommendations stay unchanged." Includes a "Back to
  [primary]" return chip.
- [x] PWA cache bumped to `gyan-v4-2026-04-26-cross-segment`.

Still TODO in Wave 7:
- [ ] `user_metadata.also_explores: string[]` field — explicit cross-segment
  interest capture. Used by Acharya for prioritising content + by web for
  surfacing cross-links. Defer until we observe actual cross-segment
  traffic (Wave 7 Part C, post-launch metrics).
- [ ] Verify `/` (home) honours `primary_segment` for first-visit redirect
  vs always showing the segment picker. Current behaviour: card grid
  always renders with primary highlighted (good), no auto-redirect (good).
  Decide post-pilot whether to add a "skip picker" toggle in Profile.

### Wave 7 — Cross-segment access architecture (NEW, 2026-04-25 strategic)

**Decision locked:** segments are LENSES, not WALLS. UPSC aspirants live on NCERT
6-12. JEE/NEET on NCERT 11-12. WBCS on WBBSE textbooks. Real users cross-pollinate
constantly. The current code already permits navigation to any segment — but the
UX/recommendations don't surface this.

- [ ] Rename `user_metadata.segment` → `user_metadata.primary_segment` (with a
  one-time migration in `Auth.tsx` / `profile/page.tsx`).
- [ ] Add `user_metadata.also_explores: string[]` (e.g.
  `["school/wbbse/class-9", "school/cbse/class-10"]`) — captures explicit
  cross-segment interest. Used by Acharya for prioritising content + by web for
  surfacing cross-links.
- [ ] Reframe Profile copy: "Primary lens · You can browse any section anytime."
- [ ] Make `/` (home) honour `primary_segment` — redirect to the segment dashboard
  on first visit but show a discoverable "Switch lens" affordance.
- [ ] Add cross-segment "Foundation" recommendations to dashboards:
  - `/competitive` UPSC users → "Build foundation: NCERT Class 8 Geography, Class 10 Polity"
  - `/competitive` WBCS users → "Build foundation: WBBSE Class 9 History, Class 10 Geography"
  - `/competitive` JEE/NEET → "Build foundation: NCERT Class 11-12 Physics/Chemistry/Biology"
- [ ] When a competitive student visits /school content, show a discreet banner:
  "📚 Building foundation for UPSC. Your competitive recommendations remain unchanged."
- [ ] **Verify settings sync end-to-end**: region, language, theme, primary_segment
  all persist AND drive the actual UI on next login. Currently `handleSaveSegment`
  persists but nothing reads it for routing — fix this loop.
- [ ] Verify Topbar segment switcher (if exists) actually swaps context. If not,
  build it as a 3-icon row (school / competitive / IT) with active state.

### Wave 8 — Sarbagya AI Chat panel (NEW, replaces broken "Talk to Sarbajna")

The Wave 2.5 link removal is honest — the destination didn't exist. But the
*concept* is wanted: a slide-in chat drawer where the student can ask
Sarbagya (the all-knowing scout agent, AGENTS.md ID 1) anything about their
syllabus. Build properly:

- [ ] Create `<SarbagyaChatDrawer>` — slide-in from right, Cmd+/ to open
- [ ] Backend route `app/api/sarbagya/route.ts` — proxies through the LLM
  router (Phase 19), uses Groq/Llama default + Sarvam-M for Bengali
- [ ] Inject student context: `primary_segment`, recent topics, mastery
  weak-spots — so questions like "explain VPC" get answered through the
  AZ-900 lens for an Azure student or generic for everyone else
- [ ] Source citation: every answer surfaces which textbook/section it
  came from (or marks "general knowledge" — important for trust chips)
- [ ] Re-add the "Talk to Sarbagya" item to CommandPalette + add a
  floating button on dashboards
- [ ] Quota / rate-limit: 50 questions / day for free users, unlimited
  for paid (Phase 22 monetisation)
- [ ] Safety: every reply runs through Dharmarakshak / Llama-Guard 3
  before display (same pipeline that gates content)

### Wave 10 — Current Affairs system for competitive exams (NEW, 2026-04-26)

**Critical analysis (decision recorded):** CA is a major exam component for
~85% of competitive recruitment exams. It is NOT a one-shot content
generation — it requires recurring ingestion + decay + dedicated UI.

**Exams that test CA (in scope):**
  - UPSC family (~30% of GS-1)
  - WBCS / WBPSC / state PSCs (~15-20%)
  - SSC CGL/CHSL/MTS (~25% as "General Awareness")
  - Banking (IBPS PO, SBI PO, RBI Grade B, NABARD, SEBI)
  - Railway (RRB NTPC, ALP)
  - Defence (NDA, CDS, AFCAT)
  - WB Police, KP SI, Excise

**Exams that DON'T need CA (out of scope):**
  - JEE / NEET / GATE / CAT / XAT — pure technical/aptitude
  - WB TET — pedagogy-focused
  - CA / CS / CMA — finance-specific only (separate sub-feed if ever)

**Scope estimate: 1-2 weeks focused work.** Components:
1. Ingestion pipeline (`agents/sarbagya_ca.py` extension):
   - Sources: PIB, The Hindu editorial digest, Indian Express explained,
     RBI press, MEA briefings, ISRO, awards/sports, WB Government feed
     (for WB-specific exams).
   - Schedule: daily 06:00 IST via GitHub Actions cron.
   - Output: dated CA cards + 3-5 derived MCQs per card.
2. Schema additions:
   - `current_affairs` content type in `pyq_bank_v2` or new table.
   - `relevance_until` date column for decay model.
   - `ca_theme` enum: international, polity, economy, science_tech,
     environment, awards, sports, defence, wb_state.
3. Audit gate (Vidushak adapt):
   - CA sources are time-bound; bypass cross-source-coverage check but
     enforce single-source-citation rule.
4. UI:
   - New `Current Affairs` tab in `ContentPanel.tsx` next to PYQ / Notes.
   - Date-stamped feed, "this week" / "this month" / "year archive" filters.
   - Per-card MCQ drill-down (uses existing InteractiveMCQ).
   - Theme tag chips.
5. Notifications:
   - Reuse `/api/notifications`. New event type `current_affairs_digest`.
   - "5 new CA questions for WBCS this week" / "RBI policy update — read".
6. Decay model:
   - Questions older than `relevance_until` hidden from default feed but
     surface in "Browse archive" filter.

**Today's scaffolding (Wave 5 byproduct):** Add a "Current Affairs"
placeholder tab in the competitive nav so the slot is reserved and students
see it's intentional. Implementation proper deferred to Wave 10.

### Wave 6 (post-sprint) — Polish from frontend-design audit
- [ ] Display+body font pair for IT section (currently single `font-sans`)
- [ ] Trust-chip redesign as brand moment (still functional, more memorable)
- [ ] Empty-state ("Scout AI on a mission") tonal alignment
- [ ] Visual system unity across School/Competitive/IT dashboards (without flattening
  segment identity)

### Notes
- Streamlit cannot be "redesigned" the way Next.js can — at most 15-20% better visually.
- IT dark theme `data-theme="aws|azure|snowflake|anthropic|google-ai|scrum"` is PROTECTED.
  The cyberpunk slate/emerald aesthetic is committed and tokenised; do not touch.
- `UI_OVERHAUL_TODO.md` historical phase items still apply but are now sequenced via this
  Wave Program. When a Wave ships, also tick the corresponding UI_OVERHAUL phase items.

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
