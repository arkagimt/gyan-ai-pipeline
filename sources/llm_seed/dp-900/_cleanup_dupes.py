"""Delete the orphaned 11 notes from the old batch that remained after cleanup."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# The old notes batch was pipeline-it-1777169889 (kept by mistake)
# The new batch IDs are from the fresh load — find and keep only those

r = (client.table("ingestion_triage_queue")
     .select("id, batch_id, payload_type, created_at")
     .eq("raw_data->>exam", "DP-900")
     .order("created_at", desc=True)
     .execute())

print(f"Total DP-900 entries: {len(r.data)}")

# Group by batch
from collections import defaultdict
batches = defaultdict(list)
for x in r.data:
    batches[x["batch_id"]].append(x)

# Sort by time, keep latest full set (should be 5 batches = 4×25 MCQs + 1×11 notes)
sorted_bids = sorted(batches.keys(), key=lambda b: batches[b][0]["created_at"], reverse=True)

# Latest 5 batches form the current load
latest_load_bids = set(sorted_bids[:5])
print(f"Latest load batch IDs: {latest_load_bids}")
keep_count = sum(len(batches[b]) for b in latest_load_bids)
print(f"Keeping {keep_count} entries from latest load")

# Delete everything else
delete_ids = []
for bid in sorted_bids[5:]:
    delete_ids.extend(x["id"] for x in batches[bid])

if delete_ids:
    print(f"Deleting {len(delete_ids)} orphaned entries...")
    for i in range(0, len(delete_ids), 50):
        chunk = delete_ids[i:i+50]
        client.table("ingestion_triage_queue").delete().in_("id", chunk).execute()
        print(f"  Deleted {len(chunk)}")
else:
    print("No orphaned entries to delete")

# Verify
r2 = (client.table("ingestion_triage_queue")
      .select("id,payload_type")
      .eq("raw_data->>exam", "DP-900")
      .execute())
types = defaultdict(int)
for x in r2.data:
    types[x["payload_type"]] += 1
print(f"\nFinal count: {len(r2.data)} entries — pyq:{types.get('pyq',0)} material:{types.get('material',0)}")
