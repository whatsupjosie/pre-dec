"""Store the newest N downloaded Drive blobs by git blob id; record Drive id -> blob. Usage: drive_take.py N id1 id2 ..."""
import glob, hashlib, json, os, sys
ids = sys.argv[2:]; n = int(sys.argv[1]); assert n == len(ids)
blobs = sorted(glob.glob("/tmp/claude-tool-results/*/mcp-Google_Drive-blob-*"), key=os.path.getmtime)[-n:]
mp = "/home/claude/drive_ls/blobs.json"; m = json.load(open(mp)) if os.path.exists(mp) else {}
os.makedirs("/home/claude/drive_ls/objects", exist_ok=True)
for fid, b in zip(ids, blobs):          # downloads were made in the same order as ids
    data = open(b, "rb").read()
    h = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    open(f"/home/claude/drive_ls/objects/{h}", "wb").write(data)
    m[fid] = dict(blob=h, size=len(data)); os.remove(b)
    print(fid, h, len(data))
json.dump(m, open(mp, "w"), indent=0)
