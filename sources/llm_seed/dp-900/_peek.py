"""Quick peek at the raw file structure."""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

text = open(r"C:\Users\arkag\.gemini\antigravity\playground\sparse-halo\jsonformatter_updated_dp900.txt", 
            "r", encoding="utf-8").read()
cleaned = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

print(f"Total: {len(cleaned):,} chars")
print(f"First 200: {cleaned[:200]}")
print(f"...")
print(f"Char 26350-26400: {cleaned[26350:26400]}")
print(f"...")

# Count top-level braces
depth = 0
objects = []
start = None
for i, ch in enumerate(cleaned):
    if ch == '{':
        if depth == 0:
            start = i
        depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0 and start is not None:
            objects.append((start, i+1))
            start = None

print(f"\nFound {len(objects)} top-level JSON objects:")
for idx, (s, e) in enumerate(objects):
    snippet = cleaned[s:s+80]
    print(f"  Object {idx+1}: chars {s}-{e} ({e-s:,} chars) — {snippet}...")
