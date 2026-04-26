"""Final verification: where are approved DP-900 MCQs?"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client
from collections import defaultdict

c = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 1. All DP-900 entries in triage, grouped by type+status
r = c.table("ingestion_triage_queue").select("id,payload_type,status").eq("raw_data->>exam", "DP-900").execute()
summary = defaultdict(int)
for x in r.data:
    summary[f"{x['payload_type']}:{x['status']}"] += 1
print("Triage queue DP-900:")
for k in sorted(summary.keys()):
    print(f"  {k}: {summary[k]}")
print(f"  Total: {len(r.data)}")

# 2. Where do approved MCQs land? Check all tables
for table in ["pyq_bank", "questions", "mcq_bank", "approved_content"]:
    try:
        r2 = c.table(table).select("id").limit(1).execute()
        print(f"\n  Table '{table}' exists ({len(r2.data)} sample)")
    except:
        pass

# 3. study_materials DP-900 count
r3 = c.table("study_materials").select("id").eq("metadata->>exam", "dp-900").execute()
print(f"\nstudy_materials dp-900: {len(r3.data)} entries")

# 4. Check if there are approved MCQs from earlier loads still in triage
r4 = c.table("ingestion_triage_queue").select("id,payload_type,status").eq("raw_data->>exam", "DP-900").eq("payload_type", "pyq").execute()
mcq_statuses = defaultdict(int)
for x in r4.data:
    mcq_statuses[x["status"]] += 1
print(f"\nDP-900 MCQs in triage by status: {dict(mcq_statuses)}")

# 5. Check AZ-900 for comparison
r5 = c.table("ingestion_triage_queue").select("id,payload_type,status").eq("raw_data->>exam", "AZ-900").execute()
az_summary = defaultdict(int)
for x in r5.data:
    az_summary[f"{x['payload_type']}:{x['status']}"] += 1
print(f"\nAZ-900 triage for comparison:")
for k in sorted(az_summary.keys()):
    print(f"  {k}: {az_summary[k]}")
