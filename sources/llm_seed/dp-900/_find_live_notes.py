"""Find and delete old DP-900 notes from the live study_materials table."""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 1. Check study_materials table structure
print("Checking study_materials table...")
r = client.table("study_materials").select("*").limit(2).execute()
if r.data:
    print(f"  Columns: {list(r.data[0].keys())}")
    # Check for DP-900 entries
    for key in r.data[0].keys():
        val = r.data[0][key]
        if isinstance(val, dict) and ("exam" in val or "DP-900" in json.dumps(val)):
            print(f"  Found exam reference in column '{key}'")

# 2. Try different filter paths to find DP-900 notes
filter_attempts = [
    ("metadata->>exam", "dp-900"),
    ("metadata->>exam", "DP-900"),
    ("raw_data->>exam", "dp-900"),
    ("raw_data->>exam", "DP-900"),
]

for col_path, val in filter_attempts:
    try:
        r2 = (client.table("study_materials")
              .select("id, created_at")
              .eq(col_path, val)
              .execute())
        if r2.data:
            print(f"\n  FOUND {len(r2.data)} entries via {col_path}={val}")
            for x in r2.data:
                print(f"    {x['id'][:16]}... [{x['created_at'][:19]}]")
    except Exception as e:
        pass  # Column doesn't exist

# 3. Try broader search - get all entries and inspect
print(f"\nAll study_materials entries:")
r3 = client.table("study_materials").select("id, created_at, metadata").limit(50).execute()
print(f"  Total in table: {len(r3.data)}")
for x in r3.data:
    meta = x.get("metadata", {})
    if isinstance(meta, dict):
        exam = meta.get("exam", meta.get("exam_code", "?"))
    else:
        exam = "?"
    print(f"  {x['id'][:16]}... [{x['created_at'][:19]}] exam={exam}")
