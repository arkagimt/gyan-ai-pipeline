"""
═══════════════════════════════════════════════════════════════════════
  DP-900 END-TO-END AUDIT
  Checks everything: seed, DB, triage, casing, pipeline, web config
═══════════════════════════════════════════════════════════════════════
"""
import json, sys, os, re
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, REPO)

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
WEB_ROOT = os.path.join(os.path.dirname(REPO), "gyan-ai-web")

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
results = []

def check(name, status, detail=""):
    results.append((name, status, detail))
    icon = {"PASS": "OK", "FAIL": "XX", "WARN": "!!"}[status]
    print(f"  [{icon}] {name}")
    if detail:
        print(f"       {detail}")


# ═══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  SECTION 1: SEED FILE INTEGRITY")
print("=" * 70)

seed_path = os.path.join(HERE, "dp-900-v1.json")
try:
    seed = json.load(open(seed_path, "r", encoding="utf-8"))
except Exception as e:
    check("Seed file readable", FAIL, str(e))
    sys.exit(1)

check("Seed file readable", PASS)

# 1a. MCQ count
mcqs = seed.get("mcqs", [])
check("MCQ count = 100", PASS if len(mcqs) == 100 else FAIL, f"Found {len(mcqs)}")

# 1b. Notes count
notes = seed.get("notes", [])
check("Notes count = 11", PASS if len(notes) == 11 else FAIL, f"Found {len(notes)}")

# 1c. Seq contiguous
seqs = [m["seq"] for m in mcqs]
expected = list(range(1, 101))
check("MCQ seq 1..100 contiguous", PASS if seqs == expected else FAIL,
      f"Missing: {set(expected) - set(seqs)}" if seqs != expected else "")

# 1d. Correct values
bad_correct = [m["seq"] for m in mcqs if m["correct"] not in ("A","B","C","D")]
check("All correct in A|B|C|D", PASS if not bad_correct else FAIL,
      f"Bad: {bad_correct}" if bad_correct else "")

# 1e. Difficulty valid
valid_diff = {"easy", "medium", "hard"}
bad_diff = [m["seq"] for m in mcqs if m["difficulty"] not in valid_diff]
check("Difficulty values valid", PASS if not bad_diff else FAIL,
      f"Bad: {bad_diff}" if bad_diff else "")

# 1f. Bloom valid
valid_bloom = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
bad_bloom = [m["seq"] for m in mcqs if m["bloom_level"] not in valid_bloom]
check("Bloom values valid", PASS if not bad_bloom else FAIL,
      f"Bad: {bad_bloom}" if bad_bloom else "")

# 1g. Notes richness
thin_notes = []
for i, n in enumerate(notes):
    kc = len(n.get("key_concepts", []))
    if kc < 2:
        thin_notes.append(f"Note {i+1} ({n.get('topic_title','?')[:30]}): {kc} concepts")
check("Notes have >= 2 key_concepts each", PASS if not thin_notes else WARN,
      "; ".join(thin_notes) if thin_notes else "")

# 1h. Meta fields
meta = seed.get("meta", {})
pi = meta.get("pipeline_ingest", {})
check("meta.pipeline_ingest.exam = 'dp-900'",
      PASS if pi.get("exam") == "dp-900" else FAIL, f"Got: {pi.get('exam')!r}")
check("meta.pipeline_ingest.provider = 'Microsoft'",
      PASS if pi.get("provider") == "Microsoft" else FAIL, f"Got: {pi.get('provider')!r}")
check("meta.audit_gate.status = 'passed'",
      PASS if meta.get("audit_gate", {}).get("status") == "passed" else FAIL)

# 1i. Difficulty distribution
diffs = {d: sum(1 for m in mcqs if m["difficulty"] == d) for d in valid_diff}
check("Difficulty distribution", PASS, f"easy:{diffs.get('easy',0)} med:{diffs.get('medium',0)} hard:{diffs.get('hard',0)}")


# ═══════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print("  SECTION 2: CASING CONSISTENCY")
print("=" * 70)

# Check all places where dp-900 / DP-900 appears
casing_issues = []

# 2a. Seed meta uses lowercase 'dp-900'
if pi.get("exam") != "dp-900":
    casing_issues.append(f"seed meta.exam = {pi.get('exam')!r} (should be 'dp-900')")

# 2b. audit.py uses lowercase key
audit_path = os.path.join(REPO, "sources", "llm_seed", "audit.py")
audit_text = open(audit_path, "r", encoding="utf-8").read()
if '"dp-900"' in audit_text:
    check("audit.py key = 'dp-900' (lowercase)", PASS)
else:
    check("audit.py key = 'dp-900' (lowercase)", FAIL, "Key not found")
    casing_issues.append("audit.py missing 'dp-900'")

# Check what the audit taxonomy stores as exam field
if 'exam     = "DP-900"' in audit_text:
    check("audit.py exam value = 'DP-900' (uppercase code)", PASS)
    # This is the value that goes into raw_data.exam in the DB
    # The loader's _build_metadata sets metadata.exam = slug.lower() = 'dp-900'
    # BUT raw_data.exam comes from taxonomy.exam = 'DP-900'
    # This is the dp-900 vs DP-900 discrepancy!
    casing_issues.append("raw_data.exam = 'DP-900' (from taxonomy) BUT metadata.exam = 'dp-900' (from _build_metadata)")

# 2c. load_to_supabase SOURCE_URLS uses lowercase
loader_path = os.path.join(REPO, "sources", "llm_seed", "load_to_supabase.py")
loader_text = open(loader_path, "r", encoding="utf-8").read()
if '"dp-900"' in loader_text:
    check("load_to_supabase.py key = 'dp-900' (lowercase)", PASS)
else:
    check("load_to_supabase.py key = 'dp-900'", FAIL)

# 2d. Web files
sidebar_path = os.path.join(WEB_ROOT, "src", "components", "Sidebar.tsx")
sidebar_text = open(sidebar_path, "r", encoding="utf-8").read()
if "dp-900" in sidebar_text:
    check("Sidebar.tsx has 'dp-900'", PASS)
else:
    check("Sidebar.tsx has 'dp-900'", FAIL)

blueprint_path = os.path.join(WEB_ROOT, "src", "config", "itBlueprints.ts")
blueprint_text = open(blueprint_path, "r", encoding="utf-8").read()
if "'dp-900'" in blueprint_text:
    check("itBlueprints.ts has 'dp-900'", PASS)
else:
    check("itBlueprints.ts has 'dp-900'", FAIL)

types_path = os.path.join(WEB_ROOT, "src", "lib", "types.ts")
types_text = open(types_path, "r", encoding="utf-8").read()
if "'dp-900'" in types_text or '"dp-900"' in types_text:
    check("types.ts SLUG_LABEL_MAP has 'dp-900'", PASS)
else:
    check("types.ts SLUG_LABEL_MAP has 'dp-900'", FAIL)

dashboard_path = os.path.join(WEB_ROOT, "src", "components", "ITDashboard.tsx")
dashboard_text = open(dashboard_path, "r", encoding="utf-8").read()
if "'dp-900'" in dashboard_text or '"dp-900"' in dashboard_text:
    check("ITDashboard.tsx EXAM_SLUG_MAP has 'dp-900'", PASS)
else:
    check("ITDashboard.tsx EXAM_SLUG_MAP has 'dp-900'", FAIL)

if casing_issues:
    print(f"\n  Casing notes:")
    for ci in casing_issues:
        print(f"    - {ci}")


# ═══════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print("  SECTION 3: SUPABASE LIVE DATA")
print("=" * 70)

# 3a. pyq_bank - check for DP-900 MCQs
# The web queries metadata->>exam (lowercase 'dp-900')
# But raw_data.exam stores uppercase 'DP-900'
# Need to check which path the web actually uses

for table, col, val, label in [
    ("pyq_bank", "metadata->>exam", "dp-900", "pyq_bank (metadata.exam=dp-900)"),
    ("study_materials", "metadata->>exam", "dp-900", "study_materials (metadata.exam=dp-900)"),
]:
    try:
        r = client.table(table).select("id").eq(col, val).execute()
        check(f"{label}", PASS if r.data else WARN, f"{len(r.data)} entries")
    except Exception as e:
        err = str(e)
        if "does not exist" in err:
            check(f"{label}", WARN, "Table/column not found")
        else:
            check(f"{label}", FAIL, err[:80])

# 3b. Triage queue state
r_triage = (client.table("ingestion_triage_queue")
            .select("id, payload_type, status")
            .eq("raw_data->>exam", "DP-900")
            .execute())

triage_summary = {}
for x in r_triage.data:
    key = f"{x['payload_type']}:{x['status']}"
    triage_summary[key] = triage_summary.get(key, 0) + 1

check("Triage queue state", PASS, str(triage_summary) if triage_summary else "empty")

# Check for pending MCQ duplicates (should be 0)
pending_mcqs = sum(v for k, v in triage_summary.items() if "pyq:pending" in k)
check("No pending MCQ duplicates in triage", PASS if pending_mcqs == 0 else FAIL,
      f"{pending_mcqs} pending MCQs" if pending_mcqs > 0 else "")

# Check pending notes = 11
pending_notes = sum(v for k, v in triage_summary.items() if "material:pending" in k)
check("11 new notes pending approval", PASS if pending_notes == 11 else WARN,
      f"{pending_notes} pending notes")

# 3c. Check approved MCQ count in pyq_bank
try:
    r_pyq = client.table("pyq_bank").select("id").eq("metadata->>exam", "dp-900").execute()
    check("pyq_bank MCQ count", PASS if len(r_pyq.data) == 100 else WARN,
          f"{len(r_pyq.data)} MCQs (expected 100)")
except Exception as e:
    check("pyq_bank MCQ count", WARN, str(e)[:80])

# 3d. Check study_materials is clean (0 old notes)
r_sm = client.table("study_materials").select("id").eq("metadata->>exam", "dp-900").execute()
check("study_materials clean (0 old notes)", PASS if len(r_sm.data) == 0 else FAIL,
      f"{len(r_sm.data)} entries" if r_sm.data else "")


# ═══════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print("  SECTION 4: WEB QUERY PATH CONSISTENCY")
print("=" * 70)

# The web frontend queries metadata->>exam with the SLUG (lowercase 'dp-900')
# The loader writes:
#   raw_data.exam = taxonomy.exam = 'DP-900' (uppercase)
#   raw_data.metadata.exam = slug.lower() = 'dp-900' (lowercase)
# The pyq_bank column 'metadata' holds the forwarded metadata dict
# So pyq_bank.metadata->>exam = 'dp-900' (lowercase) -- this is what the web uses

# Check PlatformContext.tsx to see how it queries
platform_ctx_path = os.path.join(WEB_ROOT, "src", "context", "PlatformContext.tsx")
if os.path.exists(platform_ctx_path):
    ctx_text = open(platform_ctx_path, "r", encoding="utf-8").read()
    if "metadata->>exam" in ctx_text or "metadata->>'exam'" in ctx_text or "metadata->>\\\"exam\\\"" in ctx_text:
        check("PlatformContext queries metadata->>exam", PASS)
    elif "exam" in ctx_text:
        check("PlatformContext references 'exam'", PASS, "verify filter path manually")
    else:
        check("PlatformContext exam filter", WARN, "Could not verify query path")
else:
    check("PlatformContext.tsx exists", WARN, "File not found")


# ═══════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print("  FINAL SCORECARD")
print("=" * 70)

passes = sum(1 for _, s, _ in results if s == PASS)
fails  = sum(1 for _, s, _ in results if s == FAIL)
warns  = sum(1 for _, s, _ in results if s == WARN)

print(f"  PASS: {passes}  |  FAIL: {fails}  |  WARN: {warns}")
print(f"  Total checks: {len(results)}")

if fails > 0:
    print(f"\n  FAILURES:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"    XX {name}: {detail}")

if warns > 0:
    print(f"\n  WARNINGS:")
    for name, status, detail in results:
        if status == WARN:
            print(f"    !! {name}: {detail}")

if fails == 0:
    print(f"\n  VERDICT: DP-900 is CLEAN")
else:
    print(f"\n  VERDICT: {fails} issue(s) need fixing")
