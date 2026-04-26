"""Quick check: where are the 100 DP-900 MCQs stored?"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 1. Check pyq_bank columns
r = client.table("pyq_bank").select("*").limit(1).execute()
if r.data:
    cols = list(r.data[0].keys())
    print(f"pyq_bank columns: {cols}")
    # Find which column has exam info
    for col in cols:
        val = r.data[0][col]
        if isinstance(val, dict) and ("exam" in val or "DP-900" in json.dumps(val)):
            print(f"  Column '{col}' contains exam info: exam={val.get('exam','?')}")

# 2. Try different query paths for DP-900 MCQs
for col_path, val in [
    ("raw_data->>exam", "DP-900"),
    ("raw_data->>exam", "dp-900"),
    ("exam", "dp-900"),
    ("exam", "DP-900"),
]:
    try:
        r2 = client.table("pyq_bank").select("id").eq(col_path, val).execute()
        if r2.data:
            print(f"\n  pyq_bank.{col_path} = '{val}': {len(r2.data)} MCQs")
    except:
        pass

# 3. Also check study_materials - verify the 11 notes are the NEW structured ones
r3 = client.table("study_materials").select("data_payload, created_at").eq("metadata->>exam", "dp-900").limit(2).execute()
if r3.data:
    for x in r3.data:
        dp = x["data_payload"]
        if isinstance(dp, dict):
            kc = len(dp.get("key_concepts", []))
            title = dp.get("topic_title", "?")
            print(f"\n  study_materials note: '{title[:40]}' — {kc} key_concepts [{x['created_at'][:19]}]")
