"""Open zips recursively (zips inside zips, any depth) and inventory every file by git blob id.

usage: python3 -I zipwalk.py OUT_DIR OUT_JSONL zip1 [zip2 ...]
Every entry is written under OUT_DIR/<zip name>/... ; entries whose path would escape are refused and listed.
"""
import hashlib, io, json, os, sys, zipfile
from pathlib import PurePosixPath

out_dir, out_jsonl, zips = sys.argv[1], sys.argv[2], sys.argv[3:]


def blob_id(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def norm_id(data):
    return blob_id(data.replace(b"\r\n", b"\n"))


def safe(name):
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        return None
    return str(p)


records = []


def walk(zbytes, chain, dest, depth):
    try:
        z = zipfile.ZipFile(io.BytesIO(zbytes))
    except zipfile.BadZipFile as e:
        records.append({"chain": chain, "path": None, "error": f"bad zip: {e}", "depth": depth})
        return
    for info in z.infolist():
        if info.is_dir():
            continue
        rel = safe(info.filename)
        if rel is None:
            records.append({"chain": chain, "path": info.filename, "error": "refused: escapes folder", "depth": depth})
            continue
        try:
            data = z.read(info)
        except Exception as e:
            records.append({"chain": chain, "path": rel, "error": f"unreadable: {e}", "depth": depth})
            continue
        bid = blob_id(data)
        target = os.path.join(out_dir, "_objects", bid[:2], bid)      # content-addressed: names can never collide
        if not os.path.exists(target):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(data)
        rec = {"chain": chain, "path": rel, "size": len(data), "blob": blob_id(data), "norm": norm_id(data),
               "depth": depth, "dirs_deep": len(PurePosixPath(rel).parts) - 1}
        records.append(rec)
        if rel.lower().endswith(".zip") and zipfile.is_zipfile(io.BytesIO(data)):
            walk(data, chain + [rel], None, depth + 1)


for zp in zips:
    name = os.path.basename(zp)
    with open(zp, "rb") as f:
        walk(f.read(), [name], os.path.join(out_dir, name), 1)

with open(out_jsonl, "w") as f:
    for r in records:
        f.write(json.dumps(r) + "\n")
files = [r for r in records if r.get("blob")]
print(f"files {len(files)}  errors {len(records) - len(files)}  max zip nesting {max(r['depth'] for r in records)}  "
      f"max folder depth {max((r.get('dirs_deep', 0) for r in files), default=0)}")
