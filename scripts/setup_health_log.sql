-- ═══════════════════════════════════════════════════════════════════════════════
-- Gyan AI — Vaidya Health Log Setup (Phase 16)
-- Run in Supabase SQL Editor (safe to re-run — all IF NOT EXISTS)
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── vaidya_health_log ─────────────────────────────────────────────────────────
-- One row per bhealth-check run. `report` is the full HealthReport JSON so
-- future dashboards (Phase 20) can slice by check name, latency, etc.
CREATE TABLE IF NOT EXISTS public.vaidya_health_log (
  id           BIGSERIAL PRIMARY KEY,
  run_at       TIMESTAMPTZ DEFAULT now(),
  all_ok       BOOLEAN NOT NULL,
  fail_count   INT     NOT NULL DEFAULT 0,
  source       TEXT    DEFAULT 'cli',     -- 'cli' | 'streamlit' | 'cron'
  report       JSONB   NOT NULL            -- full HealthReport.to_dict()
);

-- Index for the most common query: "show me the last N runs"
CREATE INDEX IF NOT EXISTS idx_vaidya_health_run_at
  ON public.vaidya_health_log (run_at DESC);

-- Index for "how many failures in the last 7 days"
CREATE INDEX IF NOT EXISTS idx_vaidya_health_failures
  ON public.vaidya_health_log (run_at DESC)
  WHERE all_ok = false;

-- Optional: 90-day retention. Supabase doesn't run pg_cron by default, so we
-- keep this commented — enable manually if you want auto-prune.
-- SELECT cron.schedule('vaidya_prune_90d', '0 3 * * *',
--   $$ DELETE FROM public.vaidya_health_log WHERE run_at < now() - interval '90 days' $$);
