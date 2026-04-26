"""Inspect a known dp-900 entry to find the correct filter path."""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Fetch by known ID
ID = "9ccaecf4-356d-4300-9b8a-9e4411eb5a0b"
r = client.table("ingestion_triage_queue").select("*").eq("id", ID).execute()

if r.data:
    entry = r.data[0]
    print("Columns:", list(entry.keys()))
    rd = entry.get("raw_data", {})
    print(f"\nraw_data keys: {list(rd.keys())}")
    print(f"raw_data.exam: {rd.get('exam')}")
    meta = rd.get("metadata", {})
    print(f"raw_data.metadata keys: {list(meta.keys())}")
    print(f"raw_data.metadata.exam: {meta.get('exam')}")
    print(f"\nbatch_id: {entry.get('batch_id')}")
    print(f"payload_type: {entry.get('payload_type')}")
    print(f"status: {entry.get('status')}")
else:
    print(f"Entry {ID} not found — may have been approved/deleted already")
    
    # Try a broader search
    print("\nSearching all recent entries...")
    r2 = client.table("ingestion_triage_queue").select("id,payload_type,batch_id,created_at").order("created_at", desc=True).limit(5).execute()
    for x in r2.data:
        print(f"  {x['id'][:12]}... [{x['created_at'][:19]}] {x['payload_type']}")
