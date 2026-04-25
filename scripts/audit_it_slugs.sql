-- ============================================================================
-- audit_it_slugs.sql
-- ============================================================================
-- Run these in the Supabase SQL editor to find IT rows with drifted / stray
-- exam slugs. Anything returned here is a candidate for deletion or relabel.
--
-- Canonical sidebar-id slugs (lowercase, kebab-case) — must match
-- gyan-ai-web/src/components/ITDashboard.tsx :: EXAM_SLUG_MAP values and
-- gyan-ai-web/src/config/itBlueprints.ts :: IT_BLUEPRINTS keys.
--
--   aws-cp, aws-saa, aws-dva, aws-sysops, aws-mls,
--   az-900, ai-900, dp-900, az-104, dp-700, dp-600,
--   gcp-ml, gcp-ace, gcp-pde, gemini-api, google-ai-essentials,
--   snowpro, snowpro-ade, snowpro-genai, snowpro-arch,
--   psm1, psm2, csm, pspo,
--   anthropic-prompt, anthropic-api, anthropic-safety
-- ============================================================================

-- 1. Everything approved in pyq_bank_v2, grouped by metadata->>exam.
--    Any row with a value NOT in the canonical list above is suspect.
SELECT
  metadata ->> 'exam'         AS exam_slug,
  COUNT(*)                    AS n_mcqs,
  MIN(created_at)             AS first_seen,
  MAX(created_at)             AS last_seen
FROM pyq_bank_v2
WHERE question_payload ->> 'segment' = 'it'
   OR question_payload ->> 'provider' IS NOT NULL
GROUP BY metadata ->> 'exam'
ORDER BY last_seen DESC;

-- 2. Same for study_materials (notes).
SELECT
  metadata ->> 'exam'         AS exam_slug,
  COUNT(*)                    AS n_notes,
  MIN(created_at)             AS first_seen,
  MAX(created_at)             AS last_seen
FROM study_materials
WHERE data_payload ->> 'provider' IS NOT NULL
   OR metadata    ->> 'exam'  ILIKE 'aws%'
   OR metadata    ->> 'exam'  ILIKE 'az-%'
   OR metadata    ->> 'exam'  ILIKE 'ai-%'
   OR metadata    ->> 'exam'  ILIKE 'dp-%'
   OR metadata    ->> 'exam'  ILIKE 'gcp-%'
   OR metadata    ->> 'exam'  ILIKE 'snowpro%'
   OR metadata    ->> 'exam'  IN ('psm1','psm2','csm','pspo')
GROUP BY metadata ->> 'exam'
ORDER BY last_seen DESC;

-- 3. Items approved with UPPERCASE slug (the known bug we patched).
--    Should return 0 rows. If not, patch inline:
SELECT id, metadata ->> 'exam' AS exam, created_at
FROM pyq_bank_v2
WHERE metadata ->> 'exam' ~ '[A-Z]';

SELECT id, metadata ->> 'exam' AS exam, created_at
FROM study_materials
WHERE metadata ->> 'exam' ~ '[A-Z]';

-- ──── Remediation (review before running!) ────────────────────────────────
-- UPDATE pyq_bank_v2
--   SET metadata = jsonb_set(metadata, '{exam}', to_jsonb(lower(metadata->>'exam')))
--   WHERE metadata ->> 'exam' ~ '[A-Z]';

-- 4. Orphan hunt — AWS-tagged rows possibly approved by mistake while the
--    curator was reviewing an AZ-900 batch.
SELECT
  id,
  metadata        ->> 'exam'            AS exam,
  question_payload->> 'provider'        AS provider,
  question_payload->> 'topic'           AS topic,
  LEFT(question_payload->>'question', 80) AS preview,
  created_at
FROM pyq_bank_v2
WHERE metadata ->> 'exam' LIKE 'aws%'
   OR question_payload ->> 'provider' = 'AWS'
ORDER BY created_at DESC
LIMIT 50;

-- 5. Triage queue — anything still pending with drifted slug?
SELECT
  id,
  status,
  raw_data ->> 'exam'     AS exam,
  raw_data ->> 'provider' AS provider,
  created_at
FROM ingestion_triage_queue
WHERE payload_type = 'pyq'
  AND raw_data ->> 'exam' IS NOT NULL
  AND raw_data ->> 'exam' ~ '[A-Z]'
ORDER BY created_at DESC;
