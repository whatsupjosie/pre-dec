"""Pick the project code files worth a human read, and the engine-related ones among them.

Usage: python -I candidates.py INDEX.tsv OUT.json
"""
import csv, json, re, sys
csv.field_size_limit(10**9)
CODE = ("Python", "JavaScript/TypeScript", "HTML page", "Rust")
SKIP = ("Already", "Subset", "Third-party", "Compiled", "Does not compile")
ENGINE = re.compile(r"render|captur|record|audio|camera|cam_|vcam|switch|mocap|motion|perform|timeline|sync|"
                    r"stem|mixer|meter|ffmpeg|video|stage|director|control_room|broadcast|reconstruct|glb|"
                    r"avatar|choreo|locomot|skelet|facial|lipsync|viseme|tally|program|preview|blackbox|recorder", re.I)
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8"), delimiter="\t"))
seen, cands = set(), []
for r in rows:
    if r["origin"] != "project file" or r["kind"] not in CODE or r["potential"].startswith(SKIP):
        continue
    if r["fingerprint"] in seen:
        continue
    seen.add(r["fingerprint"])
    cands.append(r)
eng = [r for r in cands if ENGINE.search(r["name"] + " " + r["location"].split(" >> ")[-1] + " " + r["what_it_is"][:400])]
json.dump(eng, open(sys.argv[2], "w"), indent=0)
print("project code candidates", len(cands), "engine-related", len(eng))
