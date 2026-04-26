"""
Delete all 33 old DP-900 notes from study_materials table.
These are buggy/thin notes from 3 duplicate loads.
After deletion, the 11 new structured notes in triage can be approved.
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 1. Find all old DP-900 notes in study_materials
r = (client.table("study_materials")
     .select("id, created_at")
     .eq("metadata->>exam", "dp-900")
     .execute())

old_notes = r.data
print(f"Found {len(old_notes)} old DP-900 notes in study_materials")

if old_notes:
    ids = [x["id"] for x in old_notes]
    client.table("study_materials").delete().in_("id", ids).execute()
    print(f"Deleted {len(ids)} old buggy notes from study_materials")

# 2. Verify study_materials is clean
r2 = (client.table("study_materials")
      .select("id")
      .eq("metadata->>exam", "dp-900")
      .execute())
print(f"Remaining DP-900 notes in study_materials: {len(r2.data)}")

# 3. Verify triage queue state
r3 = (client.table("ingestion_triage_queue")
      .select("id, payload_type, status")
      .eq("raw_data->>exam", "DP-900")
      .execute())
types = {}
for x in r3.data:
    key = f"{x['payload_type']}:{x['status']}"
    types[key] = types.get(key, 0) + 1

print(f"\nTriage queue DP-900 state:")
for key, count in sorted(types.items()):
    print(f"  {key}: {count}")

print(f"\nTotal in triage: {len(r3.data)}")
