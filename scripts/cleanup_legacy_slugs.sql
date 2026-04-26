-- =============================================================================
-- cleanup_legacy_slugs.sql — Normalise pre-Wave-1 metadata.exam slugs
-- =============================================================================
-- Wave 11 follow-up (2026-04-26): some rows in pyq_bank_v2 and study_materials
-- have metadata.exam values that don't match lowercase-kebab — uppercase
-- letters, spaces, dots, underscores, etc. They were inserted before commit
-- 3e18958 added slug enforcement to the loader.
--
-- This script:
--   STEP 1 — Diagnose: list violating rows so you can eyeball them
--   STEP 2 — Normalise: lowercase + replace common separators with hyphens
--   STEP 3 — Verify the cleanup worked (zero violators)
--   STEP 4 — Add the CHECK constraints that fix_2026_04_26_admin_bugs.sql
--            originally tried to add (now safe because all rows comply)
--
-- RUN STEPS 1-3 FIRST AS A DRY RUN. Review the output. ONLY run STEP 4 once
-- you're satisfied. Each step is in its own block with -- ── markers.
-- =============================================================================


-- ─── STEP 1 — Diagnose ───────────────────────────────────────────────────────
-- Lists every row where metadata.exam doesn't match lowercase kebab. Run
-- this first to see the scope.

-- pyq_bank_v2 violators
SELECT
  'pyq_bank_v2'        AS table_name,
  id,
  metadata ->> 'exam'  AS current_slug,
  -- preview of the question stem so you can sanity-check before touching
  LEFT(question_payload ->> 'question', 80) AS question_preview,
  created_at
FROM pyq_bank_v2
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
ORDER BY created_at DESC
LIMIT 100;

-- study_materials violators
SELECT
  'study_materials'    AS table_name,
  id,
  metadata ->> 'exam'  AS current_slug,
  LEFT(data_payload ->> 'topic_title', 80) AS topic_preview,
  created_at
FROM study_materials
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
ORDER BY created_at DESC
LIMIT 100;


-- ─── STEP 2 — Normalise (REVIEW BEFORE RUNNING) ──────────────────────────────
-- Strategy:
--   1. Lowercase the entire string
--   2. Replace runs of non-alphanumeric characters with a single hyphen
--   3. Strip leading/trailing hyphens
-- This converts e.g. "AZ-900" → "az-900", "WBCS Prelims" → "wbcs-prelims",
-- "iOS_dev.test" → "ios-dev-test".
--
-- 2026-04-26 fix: original script only had a dry-run for pyq_bank_v2 and the
-- UPDATEs were commented out. Now both tables get a dry-run + uncommented
-- UPDATE. If the auto-normalised slug doesn't match a registered slug in
-- audit.py / SLUG_LABEL_MAP / IT_TREE / curriculum, you'll need a targeted
-- UPDATE to map the row to the canonical slug (e.g. "Cloud Practitioner
-- (CLF-C02)" → "aws-cp" not "cloud-practitioner-clf-c02").

-- DRY-RUN VERSION (pyq_bank_v2 — what would change):
SELECT
  'pyq_bank_v2'                                                      AS table_name,
  id,
  metadata ->> 'exam'                                                AS current_slug,
  TRIM(BOTH '-' FROM regexp_replace(
    LOWER(metadata ->> 'exam'),
    '[^a-z0-9]+', '-', 'g'
  ))                                                                  AS proposed_slug
FROM pyq_bank_v2
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$';

-- DRY-RUN VERSION (study_materials — what would change):
SELECT
  'study_materials'                                                  AS table_name,
  id,
  metadata ->> 'exam'                                                AS current_slug,
  TRIM(BOTH '-' FROM regexp_replace(
    LOWER(metadata ->> 'exam'),
    '[^a-z0-9]+', '-', 'g'
  ))                                                                  AS proposed_slug
FROM study_materials
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$';

-- ACTUAL UPDATE — review the dry-run output first. If the proposed_slug
-- column matches a CANONICAL slug from CANONICAL_SIDEBAR_SLUGS in
-- tests/test_loader_slug.py, this auto-normalisation is safe to apply.
-- If not, do a TARGETED UPDATE instead (see notes below).

UPDATE pyq_bank_v2
  SET metadata = jsonb_set(
    metadata,
    '{exam}',
    to_jsonb(
      TRIM(BOTH '-' FROM regexp_replace(
        LOWER(metadata ->> 'exam'),
        '[^a-z0-9]+', '-', 'g'
      ))
    )
  )
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$';

UPDATE study_materials
  SET metadata = jsonb_set(
    metadata,
    '{exam}',
    to_jsonb(
      TRIM(BOTH '-' FROM regexp_replace(
        LOWER(metadata ->> 'exam'),
        '[^a-z0-9]+', '-', 'g'
      ))
    )
  )
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$';

-- TARGETED UPDATE example (uncomment + adapt for rows that need a specific
-- canonical mapping rather than regex normalisation):
--
-- UPDATE study_materials
--   SET metadata = jsonb_set(metadata, '{exam}', to_jsonb('aws-cp'::text))
--   WHERE id IN (
--     '026748eb-b5a0-42cb-8b86-902c2b53f793',
--     'cce6ac96-9c7e-405f-849d-85f3f3c624bb'
--   );


-- ─── STEP 3 — Verify ─────────────────────────────────────────────────────────
-- Both queries should return 0 rows after STEP 2 commits.

SELECT COUNT(*) AS pyq_violators_remaining
FROM pyq_bank_v2
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$';

SELECT COUNT(*) AS notes_violators_remaining
FROM study_materials
WHERE metadata ->> 'exam' IS NOT NULL
  AND metadata ->> 'exam' !~ '^[a-z0-9]+(-[a-z0-9]+)*$';


-- ─── STEP 4 — Add CHECK constraints (run only after STEP 3 returns 0/0) ──────

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

-- After STEP 4, the loader's existing in-code slug enforcement is mirrored at
-- the DB level — any future direct INSERT (psql, a future admin tool, a fork,
-- whatever) that tries to write a non-kebab exam slug fails fast with a
-- helpful error rather than silently drifting and breaking the IT_TREE
-- coverage map again.
