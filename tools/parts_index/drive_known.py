"""For downloaded Drive blobs: is the content already indexed? If not, show what it is and the closest live file."""
import ast, csv, json, subprocess, sys, collections, os
csv.field_size_limit(10**9)
fps = set()
for fn in ["zip_contents_index.tsv", "branch_files_index.tsv"]:
    for r in csv.DictReader(open("/home/claude/pre-dec/handoffs/parts_index/" + fn, encoding="utf-8"), delimiter="\t"):
        fps.add(r["fingerprint"])
m = json.load(open("/home/claude/drive_ls/blobs.json"))
B = "finish/control-room-engine"
cur = subprocess.run(["git", "-C", "/home/claude/pre-dec", "ls-tree", "-r", "--name-only", B], capture_output=True, text=True).stdout.split()
for fid in sys.argv[1:]:
    v = m[fid]; t = open("/home/claude/drive_ls/objects/" + v["blob"], encoding="utf-8-sig", errors="replace").read()
    name = sys.argv[sys.argv.index(fid)] if False else None
    print(f"\n{fid} blob {v['blob'][:10]} {v['size']}B known={v['blob'] in fps}")
    if v["blob"] in fps: continue
    try:
        mod = ast.parse(t); print("  doc:", " ".join((ast.get_docstring(mod) or "").split())[:300])
        print("  defs:", [n.name for n in mod.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))][:20])
    except SyntaxError:
        print("  head:", " | ".join(t.splitlines()[:6])[:300])
