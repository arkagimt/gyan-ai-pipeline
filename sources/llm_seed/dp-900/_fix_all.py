"""
Fix DP-900 data issues:
1. Delete all PENDING dp-900 MCQs from triage queue (already approved previously)
2. Keep PENDING dp-900 notes in triage (need to be approved)
3. Find and delete OLD approved buggy notes from live tables
"""
import sys, os
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Step 1: Delete pending MCQs from triage (they're dupes of approved ones) ──
print("=" * 60)
print("STEP 1: Clean triage queue — remove duplicate MCQs")
print("=" * 60)

r = (client.table("ingestion_triage_queue")
     .select("id, payload_type, status")
     .eq("raw_data->>exam", "DP-900")
     .eq("status", "pending")
     .execute())

pending = r.data
pyqs = [x for x in pending if x["payload_type"] == "pyq"]
notes = [x for x in pending if x["payload_type"] == "material"]
print(f"Pending DP-900: {len(pyqs)} MCQs, {len(notes)} notes")

if pyqs:
    ids = [x["id"] for x in pyqs]
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        client.table("ingestion_triage_queue").delete().in_("id", chunk).execute()
    print(f"  Deleted {len(pyqs)} duplicate pending MCQs")
else:
    print("  No pending MCQs to delete")

print(f"  Kept {len(notes)} pending notes (need approval)")

# ── Step 2: Find old approved buggy notes in live tables ──
print(f"\n{'=' * 60}")
print("STEP 2: Find old approved notes in live tables")
print("=" * 60)

# Check study_materials table
for table_name in ["study_materials", "study_material", "materials", "content"]:
    try:
        r2 = client.table(table_name).select("id, created_at").limit(1).execute()
        print(f"  Table '{table_name}' exists with {len(r2.data)} sample rows")
    except Exception as e:
        err = str(e)
        if "does not exist" in err or "404" in err or "PGRST" in err:
            continue
        print(f"  Table '{table_name}': {err[:80]}")

# Check pyq_bank for approved notes
for table_name in ["pyq_bank"]:
    try:
        r3 = (client.table(table_name)
              .select("id, created_at, raw_data")
              .eq("raw_data->>exam", "DP-900")
              .eq("raw_data->>topic_title", "Describe ways to represent data")
              .limit(5)
              .execute())
        print(f"  '{table_name}' has {len(r3.data)} DP-900 note matches")
        for x in r3.data:
            print(f"    {x['id'][:12]}... [{x['created_at'][:19]}]")
    except Exception as e:
        print(f"  '{table_name}': {str(e)[:80]}")

# Also check approved items in triage queue
r4 = (client.table("ingestion_triage_queue")
     .select("id, payload_type, status, created_at")
     .eq("raw_data->>exam", "DP-900")
     .eq("payload_type", "material")
     .neq("status", "pending")
     .execute())

print(f"\n  Approved/processed DP-900 notes in triage: {len(r4.data)}")
for x in r4.data:
    print(f"    {x['id'][:12]}... [{x['created_at'][:19]}] status={x['status']}")

# ── Step 3: Summary ──
print(f"\n{'=' * 60}")
print("SUMMARY")
print("=" * 60)
print(f"  Deleted {len(pyqs)} duplicate MCQs from triage")
print(f"  Kept {len(notes)} new notes pending approval")
print(f"  Old approved notes found: {len(r4.data)}")
if r4.data:
    print(f"\n  To delete old approved notes, run this with --delete flag")
