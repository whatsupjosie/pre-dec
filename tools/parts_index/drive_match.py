"""Match Drive-listed files against everything already indexed, by name and exact size.
Usage: python -I drive_match.py SET   ->  prints counts; writes drive_ls/SET.matched.json"""
import csv, glob, json, sys, collections
csv.field_size_limit(10**9)
S = sys.argv[1]
files = {}
for f in sorted(glob.glob(f"/home/claude/drive_ls/{S}/*.json")):
    for x in json.load(open(f))["files"]:
        files[x["id"]] = x
known = collections.defaultdict(list)   # (name, size) -> [(where, fingerprint, status)]
for r in csv.DictReader(open("/home/claude/pre-dec/handoffs/parts_index/zip_contents_index.tsv", encoding="utf-8"), delimiter="\t"):
    known[(r["name"].lower(), int(r["size"]))].append(("zip", r["fingerprint"], r["status"][:60]))
for r in csv.DictReader(open("/home/claude/pre-dec/handoffs/parts_index/branch_files_index.tsv", encoding="utf-8"), delimiter="\t"):
    known[(r["name"].lower(), int(r["size"]))].append(("branch", r["fingerprint"], r["in_current_build"][:60]))
out = []
for x in files.values():
    k = (x["title"].lower(), int(x.get("fileSize", -1)))
    m = known.get(k, [])
    out.append(dict(id=x["id"], name=x["title"], size=k[1], parent=x.get("parentId"), modified=x.get("modifiedTime"),
                    mime=x.get("mimeType"), matches=len(m), fingerprints=sorted({f for _, f, _ in m})[:3]))
json.dump(out, open(f"/home/claude/drive_ls/{S}.matched.json", "w"), indent=0)
un = [o for o in out if not o["matches"]]
print(f"{S}: {len(out)} files; {len(out) - len(un)} match a known name+size; {len(un)} unknown")
for o in sorted(un, key=lambda o: -o["size"]):
    print(f"   {o['size']:>8} {o['name'][:44]:44} {(o['modified'] or '')[:10]} {o['id']}")
