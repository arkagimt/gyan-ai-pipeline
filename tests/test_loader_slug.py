"""
test_loader_slug.py — regression test for IT exam-slug drift.

The web queries `metadata->>exam` using the Sidebar id (always lowercase
kebab-case). If the loader ever writes a slug in a different shape, the
AZ-900 "approved but invisible" bug returns.

Checks:
  1. Every key in EXAM_TAXONOMIES (audit.py) is lowercase kebab-case.
  2. Every key in EXAM_TAXONOMIES is a canonical sidebar id the web
     can route to (see CANONICAL_SIDEBAR_SLUGS below).
  3. _build_metadata in load_to_supabase.py still lowercases the slug.

We parse source with `ast` rather than importing, so the test has no
runtime dep on Groq / instructor / supabase — it runs in a bare venv.

Run:   python -m unittest tests.test_loader_slug -v
"""
from __future__ import annotations

import ast
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

AUDIT_PATH  = os.path.join(ROOT, "sources", "llm_seed", "audit.py")
LOADER_PATH = os.path.join(ROOT, "sources", "llm_seed", "load_to_supabase.py")

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Canonical sidebar-id set. Mirror of values in
# gyan-ai-web/src/components/ITDashboard.tsx :: EXAM_SLUG_MAP.
# Keep in sync — gyan-ai-web/scripts/check-it-slugs.mjs guards the
# other direction.
CANONICAL_SIDEBAR_SLUGS = {
    # AWS
    "aws-cp", "aws-saa", "aws-dva", "aws-sysops", "aws-mls",
    # Azure
    "az-900", "ai-900", "dp-900", "az-104", "dp-700", "dp-600",
    # Google Cloud
    "gcp-ml", "gcp-ace", "gcp-pde", "gemini-api", "google-ai-essentials",
    # Snowflake
    "snowpro", "snowpro-ade", "snowpro-genai", "snowpro-arch",
    # Scrum & Agile
    "psm1", "psm2", "csm", "pspo",
    # Anthropic
    "anthropic-prompt", "anthropic-api", "anthropic-safety",
}


def _parse_exam_taxonomy_keys(path: str) -> list[str]:
    """Statically extract EXAM_TAXONOMIES keys via AST (no import)."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        else:
            continue
        if name != "EXAM_TAXONOMIES":
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        keys: list[str] = []
        for k in node.value.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.append(k.value)
        return keys
    raise AssertionError(f"EXAM_TAXONOMIES dict not found in {path}")


class TestLoaderSlug(unittest.TestCase):
    def test_exam_taxonomies_keys_are_kebab(self):
        keys = _parse_exam_taxonomy_keys(AUDIT_PATH)
        self.assertTrue(keys, "EXAM_TAXONOMIES appears empty")
        bad = [k for k in keys if not SLUG_RE.match(k)]
        self.assertFalse(
            bad,
            f"EXAM_TAXONOMIES keys must be lowercase kebab-case; offenders: {bad}",
        )

    def test_exam_taxonomies_keys_are_sidebar_routable(self):
        keys = _parse_exam_taxonomy_keys(AUDIT_PATH)
        orphans = [k for k in keys if k not in CANONICAL_SIDEBAR_SLUGS]
        self.assertFalse(
            orphans,
            "EXAM_TAXONOMIES registers exams the web sidebar cannot route to: "
            f"{orphans}. Add them to EXAM_SLUG_MAP in ITDashboard.tsx, "
            "or update CANONICAL_SIDEBAR_SLUGS here.",
        )

    def test_build_metadata_lowercases_slug(self):
        """Guard the literal `.lower()` call in _build_metadata."""
        with open(LOADER_PATH, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("_build_metadata", src)
        # Find the function body
        m = re.search(
            r'def _build_metadata\([^)]*\)[^:]*:\s*"""[\s\S]*?"""([\s\S]*?)(?=\n(?:def |class |\Z))',
            src,
        )
        self.assertIsNotNone(m, "Could not locate _build_metadata body")
        body = m.group(1)
        self.assertIn(
            'exam_slug.lower()', body,
            "_build_metadata must lowercase exam_slug before writing metadata.exam "
            "— otherwise sidebar routing breaks (AZ-900 invisibility bug).",
        )

    def test_build_metadata_writes_required_fields(self):
        with open(LOADER_PATH, encoding="utf-8") as f:
            src = f.read()
        for field in ('"exam"', '"exam_code"', '"provenance_tier"',
                      '"source_type"', '"vidushak_audit"', '"confidence"'):
            self.assertIn(field, src, f"_build_metadata missing {field}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
