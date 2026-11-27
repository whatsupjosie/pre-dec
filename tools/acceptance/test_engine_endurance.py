"""30-minute endurance of the recording engine: all three recording modes at once, through the real host.

Excluded from ordinary tests/ collection (it lives in tools/acceptance). Run explicitly:

    PUBCAST_ENDURANCE_SECONDS=1800 python -m pytest -s -p no:cacheprovider tools/acceptance/test_engine_endurance.py

PowerShell 5:  $env:PUBCAST_ENDURANCE_SECONDS = "1800"; python -m pytest -s -p no:cacheprovider tools\\acceptance\\test_engine_endurance.py

The rig is the one in tests/test_recording_modes_e2e.py: run_reach.py with throwaway data, and two FFmpeg cameras
sending in real time over UDP multicast, each painting its own clock into the picture and its own tone (red
440 Hz, blue 880 Hz). Three takes run at the same time on the same host:

* camcorder, both cameras;
* main camera only, cutting between the cameras every 20 seconds (and an announcement over the PA each minute);
* data only, both cameras' sound.

Every minute it records the host's memory, each encoder's speed, the size of every take, free disk, and whether
any encoder has died. At the end every file is checked with ffprobe and decoded in full; each file's length is
compared with the take's; the picture and sound inside each file are compared with each other; the program
must hold every cut. The report (JSON) goes next to the take data and its path is printed.

What it does not prove: physical cameras, physical audio devices, a browser, or a long take on Windows.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from tests.test_recording_modes_e2e import CAMERAS, _multicast_works, mode_record, start, stop
from tests.test_intercom_real_host import _start, _stop
from tests.test_recording_faults_e2e import _senders, decodes, encoders_for

SECONDS = int(os.environ.get("PUBCAST_ENDURANCE_SECONDS", "1800"))
CUT_EVERY = float(os.environ.get("PUBCAST_ENDURANCE_CUT_EVERY", "20"))


def rss_mb(pid: int) -> float:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return float("nan")


def stream_durations(path: Path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, timeout=120)
    data = json.loads(out.stdout or "{}")
    streams = {s["codec_type"]: float(s["duration"]) for s in data.get("streams", []) if s.get("duration") not in (None, "N/A")}
    fmt = data.get("format", {}).get("duration")
    return (float(fmt) if fmt not in (None, "N/A") else None), streams


def stream_end(path: Path, kind: str):
    """Where a stream's last packet ends, read from the packets (WebM does not state per-stream durations)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", kind, "-show_entries",
                          "packet=pts_time,duration_time", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, timeout=1800)
    ends = []
    for line in out.stdout.splitlines():
        parts = [p for p in line.split(",") if p not in ("", "N/A")]
        if parts:
            ends.append(float(parts[0]) + (float(parts[1]) if len(parts) > 1 else 0.0))
    return max(ends) if ends else None


def decoded_seconds(path: Path):
    """Decode every frame and read the last timestamp FFmpeg reached (works when a container gives no duration)."""
    import re
    done = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True,
                          timeout=3600)
    times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", done.stderr)
    return done.returncode, max((int(h) * 3600 + int(m) * 60 + float(s) for h, m, s in times), default=0.0)


def test_three_recording_modes_at_once_for_thirty_minutes(tmp_path):
    import secrets
    assert 60 <= SECONDS <= 4 * 3600
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg/ffprobe not available")
    if not _multicast_works(tmp_path):
        pytest.skip("UDP multicast on the loopback interface is not available here")
    (tmp_path / "assets").mkdir()
    h = _start(tmp_path, secrets.token_urlsafe(20), first=True)
    senders = _senders(tmp_path, h)
    report = {"seconds": SECONDS, "minutes": [], "cuts": [], "pa": [], "result": {}}
    report_path = tmp_path / "engine_endurance_report.json"

    def save():
        report_path.write_text(json.dumps(report, indent=1))

    try:
        h.client.post("/api/cameras/switch", json={"target": "program", "source_id": "live_red"}).raise_for_status()
        takes = {"camcorder": "end_camcorder", "main_camera": "end_main", "data_only": "end_data"}
        t0 = time.time()
        for mode, sid in takes.items():
            start(h, sid, mode, sources=["live_red", "live_blue"])
        folders = {sid: h.data / "recordings" / sid for sid in takes.values()}
        encoders_at_start = {sid: len(encoders_for(folder)) for sid, folder in folders.items()}
        report["encoders_at_start"] = encoders_at_start
        next_cut, next_minute, next_pa, live = t0 + CUT_EVERY, t0 + 60, t0 + 30, "live_red"
        while time.time() - t0 < SECONDS:
            now = time.time()
            if now >= next_cut:
                live = "live_blue" if live == "live_red" else "live_red"
                r = h.client.post("/api/cameras/switch", json={"target": "program", "source_id": live})
                report["cuts"].append({"at": round(now - t0, 3), "to": live, "status": r.status_code})
                next_cut += CUT_EVERY
            if now >= next_pa:
                r = h.client.post("/api/intercom/announce", json={"text": f"{int((now - t0) // 60)} minutes in.",
                                                                  "rooms": ["main"], "audio": False})
                report["pa"].append({"at": round(now - t0, 1), "status": r.status_code})
                next_pa += 60
            if now >= next_minute:
                sample = {"minute": round((now - t0) / 60, 2), "host_rss_mb": round(rss_mb(h.proc.pid), 1),
                          "host_alive": h.proc.poll() is None,
                          "free_disk_mb": round(shutil.disk_usage(h.data).free / 2**20),
                          "encoders": {sid: len(encoders_for(f)) for sid, f in folders.items()},
                          "bytes": {sid: sum(p.stat().st_size for p in f.iterdir() if p.is_file())
                                    for sid, f in folders.items()}}
                meters = h.client.get("/api/program-audio/meters")
                sample["meters_status"] = meters.status_code
                report["minutes"].append(sample)
                save()
                print("ENDURANCE", json.dumps(sample), flush=True)
                assert sample["host_alive"], "the host died"
                # camcorder and data-only keep the same encoders all take; main camera's change with each cut
                for sid in ("end_camcorder", "end_data"):
                    assert sample["encoders"][sid] == encoders_at_start[sid], f"an encoder died: {sample['encoders']}"
                next_minute += 60
            time.sleep(0.2)
        took = time.time() - t0
        stopped = {sid: stop(h, sid) for sid in takes.values()}
        records = {sid: mode_record(h, sid, joined=True, timeout=1800) for sid in takes.values()}
        files = []
        paths = [(sid, Path(a["file_path"])) for sid, body in stopped.items() for a in body.get("artifacts") or []]
        assembled = records["end_main"].get("assembly", {}).get("file")
        if assembled:
            paths.append(("end_main", folders["end_main"] / assembled))
        for sid, path in paths:
            if True:
                fmt, streams = stream_durations(path)
                code, decoded = decoded_seconds(path)
                ends = {k: stream_end(path, k[0]) for k in ("video", "audio")}
                files.append({"take": sid, "file": path.name, "bytes": path.stat().st_size, "container_seconds": fmt,
                              "stream_ends": ends, "decode_exit": code, "decoded_seconds": round(decoded, 3),
                              "clean_decode": decodes(path),
                              "piece": path.name.startswith("program_0")})   # one cut's camera, not the whole take
        report["result"] = {"wall_seconds": round(took, 2), "files": files,
                            "assembly": records["end_main"].get("assembly", {}),
                            "cut_failures": [c for c in report["cuts"] if c["status"] != 200],
                            "pa_failures": [p for p in report["pa"] if p["status"] != 200],
                            "rss_first_mb": report["minutes"][0]["host_rss_mb"] if report["minutes"] else None,
                            "rss_last_mb": report["minutes"][-1]["host_rss_mb"] if report["minutes"] else None}
        save()
        print("ENDURANCE_REPORT", report_path, flush=True)

        # Judgement.
        assert not report["result"]["cut_failures"] and not report["result"]["pa_failures"]
        assert assembled and any(f["file"] == assembled for f in files), "the program was not assembled"
        for f in files:
            assert f["decode_exit"] == 0 and f["clean_decode"], f
            length = f["container_seconds"] or f["decoded_seconds"]
            if not f["piece"]:
                # every whole file runs the take (a camera from its first frame, the program from its first cut)
                assert abs(length - took) < 3.0, (f["file"], length, took)
            v, a = f["stream_ends"]["video"], f["stream_ends"]["audio"]
            if v is not None and a is not None:     # picture and sound in one file stay together
                assert abs(a - v) < 0.25, (f["file"], a, v)
        assembly = report["result"]["assembly"]
        assert assembly.get("state") == "complete" and not assembly.get("warnings"), assembly
        # every cut the director made is in the take, and each took effect promptly
        program_cuts = [c for c in records["end_main"]["program"]["cuts"] if c.get("kind") == "cut"]
        late = [c["late_by_ms"] for c in program_cuts if c.get("late_by_ms") is not None]
        report["result"]["cut_lateness_ms"] = {"count": len(late), "max": max(late, default=None),
                                               "median": sorted(late)[len(late) // 2] if late else None}
        save()
        assert len(program_cuts) == len(report["cuts"]), (len(program_cuts), len(report["cuts"]))
        assert max(late, default=0) < 2000, report["result"]["cut_lateness_ms"]
        assert len([p for p in assembly["pieces"] if p["kind"] == "segment"]) >= len(report["cuts"]), assembly
        first, last = report["result"]["rss_first_mb"], report["result"]["rss_last_mb"]
        assert last - first < 150, f"host memory grew from {first} MB to {last} MB"
    finally:
        save()
        for s in senders.values():
            s.kill()
            s.wait()
        if h.proc.poll() is None:
            _stop(h)
