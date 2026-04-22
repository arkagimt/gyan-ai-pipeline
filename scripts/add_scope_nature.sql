-- ─────────────────────────────────────────────────────────────────────────────
-- Phase 1.3 — scope + nature classification axes
-- ─────────────────────────────────────────────────────────────────────────────
-- Run in Supabase SQL editor once. Idempotent — safe to re-run.
--
-- Why:
--   `segment` (school | entrance | recruitment | it) is too coarse for the
--   state-as-lens UX. A CBSE Class 10 MCQ and a WBBSE Class 10 MCQ are both
--   `segment=school` but only the second should render inside the WB region
--   navigation; only the first should appear in a CBSE-filtered dashboard.
--
--   `scope`  = central | state | international
--   `nature` = entrance | recruitment | board | cert
--
--   Every row is tagged on write by db/supabase_loader.py via
--   models.schemas.derive_scope_nature(taxonomy). Existing rows remain NULL
--   until a backfill job tags them — the web UI treats NULL as "legacy, show
--   in all scopes" so nothing breaks during rollout.
-- ─────────────────────────────────────────────────────────────────────────────

BEGIN;

-- 1. Triage queue — new rows land here first.
ALTER TABLE public.ingestion_triage_queue
    ADD COLUMN IF NOT EXISTS scope  TEXT,
    ADD COLUMN IF NOT EXISTS nature TEXT;

COMMENT ON COLUMN public.ingestion_triage_queue.scope  IS
    'central | state | international — geographic reach of this content item.';
COMMENT ON COLUMN public.ingestion_triage_queue.nature IS
    'entrance | recruitment | board | cert — pedagogical category.';

CREATE INDEX IF NOT EXISTS idx_triage_scope
    ON public.ingestion_triage_queue (scope);
CREATE INDEX IF NOT EXISTS idx_triage_nature
    ON public.ingestion_triage_queue (nature);
CREATE INDEX IF NOT EXISTS idx_triage_scope_nature_status
    ON public.ingestion_triage_queue (scope, nature, status);


-- 2. Live bank — promoted rows from triage.
ALTER TABLE public.pyq_bank_v2
    ADD COLUMN IF NOT EXISTS scope  TEXT,
    ADD COLUMN IF NOT EXISTS nature TEXT;

COMMENT ON COLUMN public.pyq_bank_v2.scope  IS
    'central | state | international — copied from triage on promotion.';
COMMENT ON COLUMN public.pyq_bank_v2.nature IS
    'entrance | recruitment | board | cert — copied from triage on promotion.';

CREATE INDEX IF NOT EXISTS idx_pyq_bank_scope
    ON public.pyq_bank_v2 (scope);
CREATE INDEX IF NOT EXISTS idx_pyq_bank_nature
    ON public.pyq_bank_v2 (nature);
CREATE INDEX IF NOT EXISTS idx_pyq_bank_scope_nature
    ON public.pyq_bank_v2 (scope, nature);


-- 3. Check constraints — enforce the taxonomy at the DB edge.
--    NULL is allowed for legacy rows; only non-null values must be in the set.
ALTER TABLE public.ingestion_triage_queue
    DROP CONSTRAINT IF EXISTS chk_triage_scope,
    ADD  CONSTRAINT chk_triage_scope
         CHECK (scope  IS NULL OR scope  IN ('central', 'state', 'international'));

ALTER TABLE public.ingestion_triage_queue
    DROP CONSTRAINT IF EXISTS chk_triage_nature,
    ADD  CONSTRAINT chk_triage_nature
         CHECK (nature IS NULL OR nature IN ('entrance', 'recruitment', 'board', 'cert'));

ALTER TABLE public.pyq_bank_v2
    DROP CONSTRAINT IF EXISTS chk_pyq_bank_scope,
    ADD  CONSTRAINT chk_pyq_bank_scope
         CHECK (scope  IS NULL OR scope  IN ('central', 'state', 'international'));

ALTER TABLE public.pyq_bank_v2
    DROP CONSTRAINT IF EXISTS chk_pyq_bank_nature,
    ADD  CONSTRAINT chk_pyq_bank_nature
         CHECK (nature IS NULL OR nature IN ('entrance', 'recruitment', 'board', 'cert'));

COMMIT;

-- ─────────────────────────────────────────────────────────────────────────────
-- Verify:
--   SELECT scope, nature, COUNT(*) FROM public.pyq_bank_v2 GROUP BY 1,2;
--   SELECT scope, nature, COUNT(*) FROM public.ingestion_triage_queue GROUP BY 1,2;
-- Expect: new rows tagged, legacy rows NULL.
-- ─────────────────────────────────────────────────────────────────────────────
