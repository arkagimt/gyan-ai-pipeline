"""Push ONLY the 11 structured DP-900 notes to Supabase triage queue."""
import json, sys, os
sys.stdout.reconfigure(encoding="utf-8")

# Add repo root to path
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, REPO)

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

SEED = os.path.join(HERE, "dp-900-v1.json")
SOURCE_URL = "https://learn.microsoft.com/en-us/credentials/certifications/azure-data-fundamentals/"

seed = json.load(open(SEED, "r", encoding="utf-8"))
notes = seed["notes"]
meta = seed["meta"]

print(f"Pushing {len(notes)} notes to triage queue...")

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

rows = []
for note in notes:
    rows.append({
        "content_type": "study_note",
        "status": "pending",
        "payload": note,
        "metadata": {
            "exam": "dp-900",
            "provider": "microsoft",
            "authority": "microsoft",
            "segment": "it",
            "source_type": meta["source_type"],
            "generator": meta["generator"],
            "source_url": SOURCE_URL,
            "scope": "international",
            "nature": "cert",
        },
    })

result = client.table("ingestion_triage_queue").insert(rows).execute()
print(f"Inserted {len(result.data)} note entries")
print("Done!")
