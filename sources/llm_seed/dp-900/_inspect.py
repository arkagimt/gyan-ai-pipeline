import json, sys, re
sys.stdout.reconfigure(encoding="utf-8")

t = open(r"C:\Users\arkag\.gemini\antigravity\playground\sparse-halo\jsonformatter.txt", "r", encoding="utf-8").read()
c = t.replace("\r\n", " ").replace("\n", " ")
c = re.sub(r"  +", " ", c)
d = json.loads(c)

print("Top keys:", list(d.keys()))
if isinstance(d, list):
    print(f"Root is a list with {len(d)} items")
    if d:
        print(f"  First item keys: {list(d[0].keys()) if isinstance(d[0], dict) else type(d[0])}")
elif isinstance(d, dict):
    for k, v in d.items():
        if isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
            if v and isinstance(v[0], dict):
                print(f"    First item keys: {list(v[0].keys())}")
        elif isinstance(v, dict):
            print(f"  {k}: dict keys={list(v.keys())}")
        else:
            print(f"  {k}: {type(v).__name__} = {str(v)[:80]}")
