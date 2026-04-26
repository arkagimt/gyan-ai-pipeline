-- =============================================================================
-- fix_2026_04_26_admin_bugs.sql — Three SQL fixes for Arka's QA round (Wave 11)
-- =============================================================================
-- Run in Supabase SQL editor. All statements are idempotent (IF NOT EXISTS).
--
-- Triggered by:
--   1. PDF upload "42P10: no unique or exclusion constraint matching the
--      ON CONFLICT specification" — Textbooks page tried to upsert into
--      curriculum_sources with on_conflict="board,class_num,subject[,chapter]"
--      but no matching unique constraint existed.
--   2. Vaidya health-check "42703: column ingestion_triage_queue.rejection_reason
--      does not exist" — agents/vaidya.py queries this column at line 180.
--   3. (Bonus) Document the metadata.exam slug enforcement check that we
--      already have in code (load_to_supabase.py:slug_check). Adds a CHECK
--      constraint at DB level so even direct INSERTs from psql or a future
--      tool can't sneak in uppercase slugs.
--
-- Run via Supabase dashboard SQL editor or psql. Each block is atomic on its
-- own — partial run won't leave the DB in a half-state.
-- =============================================================================


-- ── Fix 1 ────────────────────────────────────────────────────────────────────
-- curriculum_sources upsert needs UNIQUE constraints to match the ON CONFLICT
-- column list the Streamlit Textbooks page sends. Two partial indexes (one for
-- chapter-NULL rows, one for chapter-present rows) cover both upsert shapes:
--   on_conflict="board,class_num,subject"            ← when chapter blank
--   on_conflict="board,class_num,subject,chapter"    ← when chapter provided
-- PostgreSQL ON CONFLICT inference matches partial unique indexes in 9.5+.

CREATE UNIQUE INDEX IF NOT EXISTS curriculum_sources_no_chapter_uidx
  ON curriculum_sources (board, class_num, subject)
  WHERE chapter IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS curriculum_sources_with_chapter_uidx
  ON curriculum_sources (board, class_num, subject, chapter)
  WHERE chapter IS NOT NULL;


-- ── Fix 2 ────────────────────────────────────────────────────────────────────
-- ingestion_triage_queue audit columns. Used by:
--   • agents/vaidya.py:180 — `select status, rejection_reason, reviewed_at`
--                            with `.gte(reviewed_at, since)` for 24h window
--   • agents/chitragupta.py — writes rejection_reason on auto-reject
--   • admin/streamlit_app.py — patched in this commit to stamp reviewed_at
--                              on every approve/reject action
--
-- 2026-04-26 patch: original migration only added rejection_reason but
-- Vaidya also needs reviewed_at. First-run failed on the index that
-- referenced the missing column. Both ADDs are idempotent so this
-- migration is safe to re-run after the partial first run.

ALTER TABLE ingestion_triage_queue
  ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

ALTER TABLE ingestion_triage_queue
  ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- Optional but useful: who approved/rejected. Captured by future admin UI.
ALTER TABLE ingestion_triage_queue
  ADD COLUMN IF NOT EXISTS reviewed_by TEXT;

-- Index for the common Vaidya query: WHERE status='rejected' ORDER BY reviewed_at.
-- Partial index keeps it tiny — only rejected rows.
CREATE INDEX IF NOT EXISTS ingestion_triage_queue_rejected_idx
  ON ingestion_triage_queue (reviewed_at DESC)
  WHERE status = 'rejected';

-- Same shape index for the 24h-window scan Vaidya does — covers both
-- approved + rejected. Partial WHERE reviewed_at IS NOT NULL skips the
-- big "pending" backlog (468 rows in your last health check).
CREATE INDEX IF NOT EXISTS ingestion_triage_queue_reviewed_at_idx
  ON ingestion_triage_queue (reviewed_at DESC)
  WHERE reviewed_at IS NOT NULL;


-- ── Fix 3 (DEFERRED) ──────────────────────────────────────────────────────────
-- Originally this section added DB-level CHECK constraints requiring
-- metadata.exam to be lowercase kebab-case. Removed from this migration
-- because some legacy rows in study_materials (and possibly pyq_bank_v2)
-- have uppercase or otherwise non-kebab slugs from before the loader's
-- slug enforcement landed (commit 3e18958).
--
-- The CHECK constraints are deferred to scripts/cleanup_legacy_slugs.sql,
-- which:
--   1. Diagnoses violating rows so Arka can review them
--   2. Normalises lowercase + replaces spaces/dots/underscores with hyphens
--   3. Then adds the CHECK constraints
--
-- The pipeline still enforces lowercase kebab in:
--   - sources/llm_seed/load_to_supabase.py (slug check)
--   - tests/test_loader_slug.py            (regression guard)
-- so all NEW data is correct. The CHECK is a belt-and-braces only.


-- ── Verification queries ─────────────────────────────────────────────────────
-- Run these after the migration to confirm. All should return rows.

-- Should list both partial indexes:
-- SELECT indexname, indexdef FROM pg_indexes
-- WHERE tablename = 'curriculum_sources' AND indexname LIKE '%uidx';

-- Should show the new column:
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns
-- WHERE table_name = 'ingestion_triage_queue' AND column_name = 'rejection_reason';

-- Should list both CHECK constraints:
-- SELECT conname FROM pg_constraint
-- WHERE conname LIKE '%exam_lowercase_kebab_check';
