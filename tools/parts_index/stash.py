"""Move the newest Drive search result into drive_ls/<set>/, report its count, new files and the next page token."""
import glob, json, os, shutil, sys
dest = f"/home/claude/drive_ls/{sys.argv[1]}"; os.makedirs(dest, exist_ok=True)
src = max(glob.glob("/tmp/claude-tool-results/*/mcp-Google_Drive-search_files-*.txt") + glob.glob("/tmp/claude-tool-results/*/toolu_*.json"), key=os.path.getmtime)
d = json.load(open(src))
if isinstance(d, list):   # wrapped form: [{"type": "text", "text": "<json>"}]
    d = json.loads(d[0]["text"])
have = set()
for f in glob.glob(dest + "/*.json"):
    have |= {x["id"] for x in json.load(open(f))["files"]}
n = len(glob.glob(dest + "/*.json")) + 1
json.dump(d, open(f"{dest}/p{n:03}.json", "w")); os.remove(src)
new = [x for x in d["files"] if x["id"] not in have]
print(f"page {n}: {len(d['files'])} files, {len(new)} new, total {len(have) + len(new)}")
print(d.get("nextPageToken", "NO MORE PAGES"))
