"""Delete ALL DP-900 entries from ingestion_triage_queue."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

c = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

r = c.table("ingestion_triage_queue").select("id").eq("raw_data->>exam", "DP-900").execute()
ids = [x["id"] for x in r.data]
print(f"Found {len(ids)} DP-900 entries in triage queue")

for i in range(0, len(ids), 50):
    chunk = ids[i:i+50]
    c.table("ingestion_triage_queue").delete().in_("id", chunk).execute()
    print(f"  Deleted {len(chunk)}")

r2 = c.table("ingestion_triage_queue").select("id").eq("raw_data->>exam", "DP-900").execute()
print(f"\nRemaining DP-900 in triage: {len(r2.data)}")
