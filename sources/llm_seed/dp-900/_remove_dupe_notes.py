"""Remove duplicate pending notes from triage. Keep 100 pending MCQs."""
import sys, os
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

c = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Get all pending DP-900 entries
r = (c.table("ingestion_triage_queue")
     .select("id, payload_type, status")
     .eq("raw_data->>exam", "DP-900")
     .eq("status", "pending")
     .execute())

summary = defaultdict(list)
for x in r.data:
    summary[x["payload_type"]].append(x["id"])

print(f"Pending: MCQs={len(summary.get('pyq',[]))}, Notes={len(summary.get('material',[]))}")

# Delete only the pending notes (already approved in study_materials)
note_ids = summary.get("material", [])
if note_ids:
    c.table("ingestion_triage_queue").delete().in_("id", note_ids).execute()
    print(f"Deleted {len(note_ids)} duplicate pending notes")

# Verify final state
r2 = (c.table("ingestion_triage_queue")
      .select("id, payload_type, status")
      .eq("raw_data->>exam", "DP-900")
      .execute())

final = defaultdict(int)
for x in r2.data:
    final[f"{x['payload_type']}:{x['status']}"] += 1

print(f"\nFinal triage state:")
for k in sorted(final.keys()):
    print(f"  {k}: {final[k]}")

# Also confirm study_materials
r3 = c.table("study_materials").select("id").eq("metadata->>exam", "dp-900").execute()
print(f"\nLive study_materials: {len(r3.data)} notes")
