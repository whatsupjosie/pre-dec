"""Write handoffs/parts_index/drive_folders_index.tsv from every Drive folder listing in /home/claude/drive_ls."""
import csv, glob, json, os
csv.field_size_limit(10**9)
FOLDERS = {"debugged": ("pubcast_complete_debugged_2026-05-08", "1vOOX-CbaYiF8J8aSzrOV21evR55gwV8n"),
           "codex": ("codex_construction_pubcast_20260614", "1_A_yjDZxhfL8B3Fm3MPXKMNz5K2B9Y96"),
           "pubblocks": ("codex_construction_pubcast_20260614_pubblocks", "192ISPO4EeHV-Hr6qfymEUQOsjM0DI9p2"),
           "wiring": ("codex_current_wiring_file_copies_20260615 + codex_ready_wiring_file_copies_20260615_133303 + codex_autonomous_session_planning",
                      "1ptCvocK0cVDj5kyD1tNk63B_ov8R4rO_ / 1mLKxDiLWqxT5ludSMX1-Nw1r0FjPC1XB / 1-mcRzMq4RFDH-dr_JSoCADVPmh5g-8zK"),
           "rubbish": ("rubbish + duplicates + big_zip_root", "1bN5Y93EQgDZ5QPAtP8NSpZOf8EvNlgIV / 1HvEU6rCeOO2Omg8JoMFI-RqvoF_8iEy2 / 1QQzfQCA3dguuzWk3recog5b38X20OJgK")}
blobs = json.load(open("/home/claude/drive_ls/blobs.json"))
fps = {}
for fn in ["zip_contents_index.tsv", "branch_files_index.tsv"]:
    for r in csv.DictReader(open("/home/claude/pre-dec/handoffs/parts_index/" + fn, encoding="utf-8"), delimiter="\t"):
        fps.setdefault(r["fingerprint"], r.get("status") or r.get("in_current_build"))
rows, seen = [], set()
dl_by_ns = {}
for mf in glob.glob("/home/claude/drive_ls/*.matched.json"):
    for o in json.load(open(mf)):
        if o["id"] in blobs: dl_by_ns[(o["name"].lower(), o["size"])] = o["id"]
for mf in sorted(glob.glob("/home/claude/drive_ls/*.matched.json")):
    s = os.path.basename(mf).split(".")[0]
    key = next(k for k in FOLDERS if s.startswith(k))
    for o in json.load(open(mf)):
        if o["id"] in seen: continue
        seen.add(o["id"])
        b = blobs.get(o["id"], {}).get("blob")
        if b:
            how = "DOWNLOADED and hashed"
            fp = b; st = ("already indexed: " + str(fps[b])[:120]) if b in fps else "NEW: content in no zip or branch tip"
        elif o["matches"]:
            how = "name and exact size match an indexed file (5 of 5 sampled were byte-identical)"
            fp = ",".join(o["fingerprints"]); st = "already indexed (by name and size)"
        elif o["size"] > 10_000_000:
            how = "too large for the Drive connector (over 10 MB)"; fp = ""; st = "NOT OPENED"
        elif (o["name"].lower(), o["size"]) in dl_by_ns:
            other = dl_by_ns[(o["name"].lower(), o["size"])]
            how = f"same name and size as Drive file {other}, which was downloaded"
            fp = blobs[other]["blob"]; st = ("already indexed: " + str(fps[fp])[:120]) if fp in fps else "NEW: content in no zip or branch tip (same as the downloaded copy)"
        else:
            how = "not downloaded"; fp = ""; st = "UNKNOWN"
        rows.append([o["name"], FOLDERS[key][0], FOLDERS[key][1], o["id"], o.get("parent") or "", o["size"], (o.get("modified") or "")[:10], how, st, fp])
with open("/home/claude/pre-dec/handoffs/parts_index/drive_folders_index.tsv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    w.writerow(["name", "drive_folder", "drive_folder_id", "drive_file_id", "drive_parent_folder_id", "size", "modified", "how_identified", "status", "fingerprint"])
    w.writerows(sorted(rows, key=lambda r: (r[1], r[0].lower())))
import collections
print(len(rows), collections.Counter(r[8].split(":")[0] for r in rows))
for r in rows:
    if r[8].startswith(("NEW", "NOT", "UNKNOWN")): print("  ", r[8][:40], r[0], r[5], r[3])
