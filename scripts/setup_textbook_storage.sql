-- ═══════════════════════════════════════════════════════════════════════════════
-- Gyan AI — Textbook Storage Setup
-- Run in Supabase SQL Editor (safe to re-run — all IF NOT EXISTS)
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── 1. curriculum_sources table ───────────────────────────────────────────────
-- Maps curriculum nodes to PDFs stored in Supabase Storage bucket 'textbook-pdfs'
CREATE TABLE IF NOT EXISTS public.curriculum_sources (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  board         TEXT NOT NULL,        -- 'WBBSE' | 'CBSE' | 'ICSE' | 'WBCHSE'
  class_num     INT  NOT NULL,        -- 1–12
  subject       TEXT NOT NULL,        -- 'Bengali' | 'Mathematics' | 'Physical Science'
  chapter       TEXT,                 -- NULL = full textbook; 'Electricity' = chapter-specific
  storage_path  TEXT NOT NULL,        -- path inside 'textbook-pdfs' bucket
                                      -- e.g. 'wbbse/1/bengali.pdf'
  display_name  TEXT,                 -- human-friendly label shown in Streamlit
  file_size_kb  INT,                  -- for display purposes
  is_active     BOOLEAN DEFAULT true,
  uploaded_at   TIMESTAMPTZ DEFAULT now(),
  uploaded_by   TEXT DEFAULT 'admin'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_curriculum_sources_node
  ON public.curriculum_sources (board, class_num, subject, chapter)
  WHERE chapter IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_curriculum_sources_node_null
  ON public.curriculum_sources (board, class_num, subject)
  WHERE chapter IS NULL;

CREATE INDEX IF NOT EXISTS idx_curriculum_sources_board_class
  ON public.curriculum_sources (board, class_num);

-- ── 2. RLS ────────────────────────────────────────────────────────────────────
ALTER TABLE public.curriculum_sources ENABLE ROW LEVEL SECURITY;

-- Service role (pipeline + Streamlit admin) can do everything
DROP POLICY IF EXISTS "Service role full access" ON public.curriculum_sources;
CREATE POLICY "Service role full access"
  ON public.curriculum_sources FOR ALL
  USING (true)
  WITH CHECK (true);

-- ── 3. Storage bucket ─────────────────────────────────────────────────────────
-- Run this separately in the Supabase Dashboard → Storage → New Bucket:
--   Name:    textbook-pdfs
--   Public:  NO  (private — accessed via service role key only)
--
-- Or via SQL (may require enabling storage extension first):
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('textbook-pdfs', 'textbook-pdfs', false)
-- ON CONFLICT (id) DO NOTHING;

-- ── DONE ──────────────────────────────────────────────────────────────────────
-- Next steps:
-- 1. Run this SQL in Supabase SQL Editor
-- 2. Create 'textbook-pdfs' bucket in Supabase Storage (private)
-- 3. Upload PDFs via Streamlit admin → 📚 Textbooks page
-- 4. Pipeline will auto-fetch the PDF when running for that board/class/subject
