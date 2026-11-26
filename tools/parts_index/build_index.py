"""Build the parts index log from the identified catalogs. Output: handoffs/parts_index/ in the pre-dec checkout."""
import collections, json, os, re

OUT = "/home/claude/pre-dec/handoffs/parts_index"
os.makedirs(os.path.join(OUT, "by_source"), exist_ok=True)
B = "/home/claude/bigzip"
recs = json.load(open(f"{B}/catalog_raw.json"))
ident = json.load(open(f"{B}/identified.json"))
bident = json.load(open(f"{B}/branch_identified.json"))
idx = json.load(open(f"{B}/index.json"))
import subprocess as _sp
cur_by_blob = collections.defaultdict(list)   # every current path for a content, not just one
for _line in _sp.run(["git", "-C", "/home/claude/pre-dec", "ls-tree", "-r", "finish/control-room-engine"],
                     capture_output=True, text=True, check=True).stdout.splitlines():
    _meta, _path = _line.split("\t", 1)
    if not _path.startswith(("handoffs/parts_index/", "tools/parts_index/")):
        cur_by_blob[_meta.split()[2]].append(_path)

DRIVE_IDS = {
    "pubcast_camera_engine__1_.zip": "1LELn92u8dQ2UU8LoRrd1PB-X58tSqv0S", "companion core.zip.zip": "15uvubKFRR60zI_9WUIZxftJXHgJK7b8u",
    "files (51).zip": "1XGnLu-T_AxrkQ0zttit-9Kfxc4CvRrDP",
    "visual_patch_kit_for_big_zip_20260611_20260611_172957.zip": "1bcRU6aEqMtxFzs39qpslXcys5mKa1ff9",
    "files (49).zip": "1ZSo47kLXRd1gRtkiJ6ZteWqROksrm0eH", "files (41).zip": "1Hmu4Bw2Jm3YwWv_W5WJAbo38CvfCdL51",
    "files (39) - Copy.zip": "1dU-Ticy55ZEPl7x06LagUkZHea3rs-VE", "codex_file_copies_20260615_125529.zip": "1cGqB5s8wzllmMITYGSapCaKGjBqVA8_S",
    "codex_autonomous_session_planning_20260614.zip": "1f7W2Gs6AdOm9FrRAr7nEGY1toBuWJ64R",
    "handoff_package_visual_patch_adaptive_props_20260610_210745.zip": "13-84LydcoQaA2MTnM3eiW46lNX_V1e-M",
    "Slightly older still good. use for referene parts and ideas.zip": "1SwzA3x5iZmwBRrrxnC0aNUlXHE674Sy1",
    "companion core  parroting moduels.zip": "1qChOaYgClvSZEddbbhXRMLv5N3c2TCak", "Pub moduals not all.zip.zip": "1D1BY96g1oUr1ICNDdLW7Ud0nzp2PloFH",
    "PUBCAST_FIRST_PRIME_UPLOAD_PACKAGE_20260618_063754.zip": "1Nd8BEffsxxZ8ekxnDBbITnDuIE2iaabs",
}
repo_zip_rows = [l.rstrip("\n").split("\t") for l in open("/home/claude/scratch/repo_zips.tsv")]
repo_zip_locs = collections.defaultdict(list)
for b, s, ref, p in repo_zip_rows:
    repo_zip_locs[b[:8]].append(f"GitHub {ref.split('/', 1)[0]} branch {ref.split('/', 1)[1]}: {p}")


def container(top):
    """Where the outermost zip itself can be found."""
    if top in DRIVE_IDS:
        extra = " ; also GitHub The-Prime (branches main, assembled-pubcast, room-pictures-2026-10-27), first commit 5a4cfe0" \
            if top.startswith("PUBCAST_FIRST_PRIME_UPLOAD") else ""
        return f"Drive whatsupjosie / big zip / {top} (file id {DRIVE_IDS[top]}){extra}"
    m = re.match(r"([0-9a-f]{8})__(.+?)__(.+)$", top)
    if m:
        locs = repo_zip_locs.get(m.group(1), [])
        return " ; ".join(locs[:3]) + (f" ; and {len(locs) - 3} more (see branch_files_index.tsv, fingerprint of the zip {m.group(1)})" if len(locs) > 3 else "")
    return top


def clean(s, n=230):
    s = " ".join(str(s or "").split()).replace("\t", " ").replace("|", "/")
    return s[:n] + ("..." if len(s) > n else "")


def what_it_is(e):
    k = e.get("kind", "")
    parts = []
    if e.get("doc"):
        parts.append(e["doc"].split(". ")[0])
    elif e.get("title"):
        parts.append("page: " + e["title"])
    elif e.get("headings"):
        parts.append("document: " + " / ".join(e["headings"][:3]))
    elif e.get("summary"):
        parts.append(e["summary"])
    if e.get("routes"):
        parts.append("routes: " + ", ".join(e["routes"][:6]))
    if e.get("top_defs"):
        parts.append("defines: " + ", ".join(e["top_defs"][:8]))
    if e.get("keys"):
        parts.append("keys: " + ", ".join(map(str, e["keys"][:8])))
    if not parts:
        parts.append(k)
    return clean(" — ".join(parts), 300)


def quality(e):
    k = e.get("kind", "")
    q = [k]
    if k == "Python":
        q.append("compiles" if e.get("compiles") else f"DOES NOT COMPILE ({e.get('syntax_error')})")
        if e.get("compiles"):
            q.append(f"{e.get('n_defs', 0)} functions, {e.get('n_classes', 0)} classes")
            if e.get("empty_functions"):
                q.append(f"{e['empty_functions']} empty/raise-only functions")
            if e.get("is_test"):
                q.append("test file")
    elif k == "JSON data" and e.get("valid_json") is False:
        q.append("INVALID JSON")
    if e.get("lines"):
        q.append(f"{e['lines']} lines")
    if e.get("stub_markers"):
        q.append(f"{e['stub_markers']} stub/TODO/mock words")
    if not e.get("lines"):
        q.append(f"{e.get('size', 0)} bytes")
    return clean("; ".join(q), 200)


CODE = {"Python", "JavaScript/TypeScript", "HTML page", "Rust"}
THIRD_PARTY = re.compile(r"(^|/)(site-packages|dist-packages|node_modules|\.venv|venv|vendor|target|__pycache__|\.git)/", re.I)


def origin(inner_path):
    m = THIRD_PARTY.search(inner_path.replace("\\", "/"))
    return f"third-party or build output (under {m.group(2)}/)" if m else "project file"


def status_and_potential(e, status, vs):
    if status == "A_current":
        return "IN CURRENT BUILD (identical content)", "Already in the build; nothing to harvest."
    if status == "B_other_branch":
        st = "IN A GIT BRANCH, NOT IN THE CURRENT BUILD"
    else:
        st = "NOT IN ANY REPO BRANCH (exists only inside this zip)"
    k = e.get("kind", "")
    if k == "compiled Python bytecode (.pyc)":
        return st, "Compiled cache, not source; value only if its .py source is lost."
    if vs:
        where = f"closest current file with this name ({vs.get('path_folders_matched', 0)} matching folders): {vs['current_path']}"
        if vs.get("current_empty"):
            return st + f"; {where} is empty", "The current file of this name is empty: this one has content; check whether it is needed."
        st += f"; differs from {where}: {vs['lines_only_here']} lines only here, {vs['lines_only_current']} only in current"
        if vs["lines_only_here"] == 0:
            pot = "Subset of the current version (older or trimmed); nothing new."
        elif vs["lines_only_here"] <= 5:
            pot = f"Near-identical to current; check the {vs['lines_only_here']} lines only here."
        elif vs["lines_only_current"] > 3 * vs["lines_only_here"]:
            pot = "Mostly older than current; read the lines only here before discarding."
        else:
            pot = "Different version with substantial content of its own: candidate to read and compare."
        return st, pot
    if k in CODE:
        if k == "Python" and not e.get("compiles"):
            return st, "Does not compile; reference only unless repaired."
        if e.get("is_test"):
            return st, "Test file not in the build: may cover behavior worth keeping."
        return st, "Code with no same-named file in the build: candidate to read for missing parts."
    if k == "document":
        return st, "Notes/handoff not in the build: read for decisions or lost context."
    if "image" in k or "GLB" in k or "WAV" in k or "audio" in k or "video" in k:
        return st, "Media asset not in the build: check whether a screen or set still needs it."
    if k == "zip archive":
        return st, "Nested zip: opened, its files are listed under it."
    return st, "Data/other file not in the build."


# ---- zip contents: one row per occurrence -------------------------------------------------------------------
rows = []
by_source = collections.defaultdict(list)
for r in recs:
    e = ident[r["blob"]]
    top = r["chain"][0]
    inner = " > ".join(r["chain"][1:] + [r["path"]])
    st, pot = status_and_potential(e, r["status"], e.get("vs_current"))
    org = origin(inner)
    if org != "project file" and r["status"] != "A_current":
        pot = "Third-party library, vendored copy or build output bundled in the zip, not PubCast code: no harvest value."
    if r["status"] == "A_current":
        paths = cur_by_blob.get(r["blob"], [])
        cp = (sorted(paths, key=lambda q: (q.startswith("recovery/"), len(q))) or [None])[0]
        st += f" at {cp}" if cp else " (same text apart from line endings)"
        if paths and all(q.startswith("recovery/") for q in paths):
            # In the tree, but only as a parked recovery copy: not live, nothing imports it from there.
            st = st.replace("IN CURRENT BUILD (identical content)", "IN CURRENT BUILD ONLY AS A PARKED COPY under recovery/ (identical content)")
            if org == "project file":
                pot = "Parked under recovery/, not live: check whether it should be wired in."
    elif r["status"] == "B_other_branch":
        first = bident.get(r["blob"], {}).get("locations", ["?"])[0]
        st += f" (e.g. {first})"
    row = {"name": os.path.basename(r["path"]), "origin": org, "location": f"{container(top)} >> {inner}",
           "zip_nesting": r["depth"], "folder_depth": r["dirs_deep"], "size": r["size"], "kind": e.get("kind", ""),
           "what_it_is": what_it_is(e), "status": st, "quality": quality(e), "potential": pot,
           "fingerprint": r["blob"], "same_content_count": e.get("occurrences", 1)}
    rows.append(row)
    by_source[top].append(row)

cols = ["name", "origin", "location", "zip_nesting", "folder_depth", "size", "kind", "what_it_is", "status", "quality", "potential",
        "fingerprint", "same_content_count"]
with open(os.path.join(OUT, "zip_contents_index.tsv"), "w", encoding="utf-8") as f:
    f.write("\t".join(cols) + "\n")
    for row in sorted(rows, key=lambda x: x["location"]):
        f.write("\t".join((clean(row[c], 100000) if c == "location" else clean(row[c], 600)) if isinstance(row[c], str) else str(row[c]) for c in cols) + "\n")

for top, items in by_source.items():
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", top)[:120]
    with open(os.path.join(OUT, "by_source", safe + ".md"), "w", encoding="utf-8") as f:
        f.write(f"# {top}\n\nWhere: {container(top)}\n\n{len(items)} files. Status counts: "
                + ", ".join(f"{k}: {v}" for k, v in collections.Counter(i['status'].split(';')[0].split(' (')[0].split(' at ')[0] for i in items).items())
                + "\n\n| File (path inside the zip) | What it is | Status | Quality | Potential |\n|---|---|---|---|---|\n")
        for i in sorted(items, key=lambda x: x["location"]):
            inner = i["location"].split(" >> ", 1)[1]
            f.write(f"| {clean(inner, 400)} | {clean(i['what_it_is'], 200)} | {clean(i['status'], 160)} | {clean(i['quality'], 120)} | {clean(i['potential'], 120)} |\n")

# ---- every file in every branch tip ---------------------------------------------------------------------------
def in_current_text(blob, e):
    paths = cur_by_blob.get(blob, [])
    if not paths:
        return "yes (same text apart from line endings): " + str(e.get("current_path")) if e.get("in_current") else "no"
    live = sorted(paths, key=lambda q: (q.startswith("recovery/"), len(q)))[0]
    if all(q.startswith("recovery/") for q in paths):
        return "only as a parked copy, not live: " + live
    return "yes: " + live


bcols = ["name", "locations", "n_locations", "size", "kind", "what_it_is", "in_current_build", "quality", "fingerprint", "also_inside_zips"]
with open(os.path.join(OUT, "branch_files_index.tsv"), "w", encoding="utf-8") as f:
    f.write("\t".join(bcols) + "\n")
    for blob, e in sorted(bident.items(), key=lambda x: x[1]["locations"][0]):
        name = os.path.basename(e["locations"][0].split(":", 1)[1])
        locs = " ; ".join(e["locations"][:40]) + (f" ; and {len(e['locations']) - 40} more" if len(e["locations"]) > 40 else "")
        vals = [name, locs, e["n_locations"], e["size"], e.get("kind", ""), what_it_is(e),
                in_current_text(blob, e), quality(e), blob, "yes" if e.get("also_in_zips") else "no"]
        f.write("\t".join(clean(v, 4000) if isinstance(v, str) else str(v) for v in vals) + "\n")

# ---- counts for the summary -----------------------------------------------------------------------------------
stats = {
    "zip_file_entries": len(recs), "zip_distinct_contents": len(ident),
    "zip_status": collections.Counter(r["status"] for r in recs),
    "zip_distinct_status": collections.Counter(e["status"] for e in ident.values()),
    "max_zip_nesting": max(r["depth"] for r in recs), "max_folder_depth": max(r["dirs_deep"] for r in recs),
    "sources": len(by_source), "branch_distinct_files": len(bident),
    "branch_refs": len({l.split(':', 1)[0] for e in bident.values() for l in e["locations"]}),
}
json.dump(stats, open(os.path.join(OUT, "stats.json"), "w"), indent=1, default=dict)
print(json.dumps(stats, default=dict, indent=1))
