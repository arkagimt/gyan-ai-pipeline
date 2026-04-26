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
-- ingestion_triage_queue.rejection_reason column. Used by:
--   • agents/vaidya.py (triage_rate health check)
--   • agents/chitragupta.py (writes the reason on rejection)
--   • models/schemas.py (TriageRow.rejection_reason: Optional[str])
-- Nullable text so historical rows without a reason stay valid.

ALTER TABLE ingestion_triage_queue
  ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Index for the common Vaidya query: WHERE status='rejected' ORDER BY reviewed_at.
-- Partial index keeps it tiny — only rejected rows.
CREATE INDEX IF NOT EXISTS ingestion_triage_queue_rejected_idx
  ON ingestion_triage_queue (reviewed_at DESC)
  WHERE status = 'rejected';


-- ── Fix 3 (DEFENSIVE) ─────────────────────────────────────────────────────────
-- Document via CHECK constraint that metadata.exam must be lowercase kebab-case
-- when present. Our pipeline enforces this in load_to_supabase.py + tests/
-- test_loader_slug.py, but a CHECK at DB level is a belt-and-braces guard
-- against any future tool / direct psql INSERT bypassing the loader.
--
-- Note: not adding to ingestion_triage_queue because raw_data is freeform
-- and may legitimately contain different exam keys.

ALTER TABLE pyq_bank_v2
  DROP CONSTRAINT IF EXISTS pyq_bank_v2_exam_lowercase_kebab_check;
ALTER TABLE pyq_bank_v2
  ADD CONSTRAINT pyq_bank_v2_exam_lowercase_kebab_check
  CHECK (
    metadata ->> 'exam' IS NULL
    OR metadata ->> 'exam' ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
  );

ALTER TABLE study_materials
  DROP CONSTRAINT IF EXISTS study_materials_exam_lowercase_kebab_check;
ALTER TABLE study_materials
  ADD CONSTRAINT study_materials_exam_lowercase_kebab_check
  CHECK (
    metadata ->> 'exam' IS NULL
    OR metadata ->> 'exam' ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
  );


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
