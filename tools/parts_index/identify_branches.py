"""Identify every distinct file in every branch tip of every repo (from git), with the same extractor."""
import json, subprocess, sys, os, collections, importlib.util
spec = importlib.util.spec_from_file_location("ident_funcs", "/home/claude/scratch/ident_funcs.py")
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
idx = json.load(open("/home/claude/bigzip/index.json"))
cur = idx["cur"]; curnorm = idx["curnorm"]
zipident = json.load(open("/home/claude/bigzip/identified.json"))
refs = subprocess.run(["git", "-C", "/home/claude/allrepos", "for-each-ref", "--format=%(refname:short)", "refs/remotes"], capture_output=True, text=True).stdout.split()
where = collections.defaultdict(list)
for r in refs:
    out = subprocess.run(["git", "-C", "/home/claude/allrepos", "ls-tree", "-r", "-l", r], capture_output=True, text=True).stdout
    for line in out.splitlines():
        meta, path = line.split("\t", 1); m = meta.split()
        if m[1] == "blob":
            where[m[2]].append(f"{r}:{path}")
p = subprocess.Popen(["git", "-C", "/home/claude/allrepos", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
out = {}
for i, (blob, locs) in enumerate(where.items()):
    p.stdin.write((blob + "\n").encode()); p.stdin.flush()
    hdr = p.stdout.readline().split(); size = int(hdr[2]); data = p.stdout.read(size); p.stdout.read(1)
    path = locs[0].split(":", 1)[1]
    ext = os.path.splitext(path.lower())[1] or "(none)"
    ent = F.identify(data, ext)
    ent.update(blob=blob, size=size, ext=ext, locations=locs, n_locations=len(locs),
               in_current=blob in cur, current_path=cur.get(blob), also_in_zips=blob in zipident)
    out[blob] = ent
    if i % 2000 == 0: print(i, file=sys.stderr)
json.dump(out, open("/home/claude/bigzip/branch_identified.json", "w"))
print("branch distinct files identified", len(out))
