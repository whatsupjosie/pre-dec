"""Faults during a take, through the real host: an encoder dies, the disk fills, the host itself is killed.

Real host (``run_reach.py``), real FFmpeg cameras over UDP multicast (the same rig as test_recording_modes_e2e.py),
real files judged afterwards with ffprobe and a full decode. Each fault is injected the way it happens on a
laptop: an FFmpeg process killed with SIGKILL, a filler file taking the last of a small disk, the host process
killed with SIGKILL and started again on the same data folder.

What a take must do under each fault:
* the take ends when asked, the host stays up, and the next take records normally;
* the report names what went wrong, for the camera it went wrong on;
* every file the take hands over decodes from start to end (nothing half-written is passed off as a recording);
* after the host is killed, no encoder keeps running on its own, and the take comes back as interrupted.

Skips without ffmpeg/ffprobe, multicast on the loopback interface, or (for the disk test) the right to mount tmpfs.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from tests.test_intercom_real_host import _start, _stop
from tests.test_recording_modes_e2e import CAMERAS, FPS, RAMP, _multicast_works, mode_record, probe, start, stop

PROFILE = "web_stream"


def decodes(path: Path) -> bool:
    """The whole file decodes with no error (ffprobe alone accepts files that stop half way)."""
    done = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"],
                          capture_output=True, text=True, timeout=300)
    return done.returncode == 0 and not done.stderr.strip()


def playable_seconds(path: Path) -> float:
    """How much of the file decodes, read from FFmpeg's own progress (a file cut short by a full disk ends early)."""
    done = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True,
                          timeout=300)
    import re
    times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", done.stderr)
    return max((int(h) * 3600 + int(m) * 60 + float(s) for h, m, s in times), default=0.0)


def media_files(folder: Path):
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in (".webm", ".mp4", ".mkv",
                                                                                          ".mov", ".wav"))


def encoders_for(folder: Path):
    """PIDs of FFmpeg processes writing into ``folder`` (read from /proc, the way an operator would find them)."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if cmd and cmd[0].endswith(b"ffmpeg") and any(str(folder).encode() in part for part in cmd):
            found.append(int(entry.name))
    return found


def _senders(work: Path, host):
    senders = {}
    for camera, (group, hz, rb) in CAMERAS.items():
        url = f"udp://{group}:5004"
        senders[camera] = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-nostdin", "-re",
             "-f", "lavfi", "-i", f"color=c=black:s=160x90:r={FPS},geq={rb}:g='mod(T*{RAMP}\\,{RAMP * 10})'",
             "-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=48000",
             "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-g", "10", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-f", "mpegts", url + "?ttl=0&pkt_size=1316"],
            stdout=subprocess.DEVNULL, stderr=open(work / f"{camera}.log", "w"))
        register(host, camera, url)
    time.sleep(1.5)
    return senders


def register(host, camera, url):
    r = host.client.post("/api/cameras/register", json={"source_id": camera, "name": camera, "transport": "srt",
                                                        "endpoint": url + "?reuse=1", "location": "studio"})
    assert r.status_code == 200, r.text


def session_dir(host, session_id):
    return host.data / "recordings" / session_id


def _kill_host(h):
    h.client.close()
    h.proc.send_signal(signal.SIGKILL)
    h.proc.wait(10)
    h.log.close()


@pytest.fixture(scope="module")
def rig(tmp_path_factory):
    import secrets
    work = tmp_path_factory.mktemp("faults")
    if not _multicast_works(work):
        pytest.skip("UDP multicast on the loopback interface is not available here")
    (work / "assets").mkdir()
    password = secrets.token_urlsafe(20)
    h = _start(work, password, first=True)
    senders = _senders(work, h)
    r = SimpleNamespace(work=work, host=h, senders=senders, password=password)
    yield r
    for s in senders.values():
        s.kill()
        s.wait()
    if r.host.proc.poll() is None:
        _stop(r.host)


def program(host, camera):
    r = host.client.post("/api/cameras/switch", json={"target": "program", "source_id": camera})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("mode", ["camcorder", "main_camera", "data_only"])
def test_an_encoder_killed_mid_take_is_named_and_everything_handed_over_decodes(rig, mode):
    h = rig.host
    program(h, "live_red")
    sid = f"kill_{mode}"
    start(h, sid, mode, sources=["live_red", "live_blue"])
    folder = session_dir(h, sid)
    time.sleep(3)
    pids = encoders_for(folder)
    assert len(pids) >= 2, pids
    # the one that matters most in each mode: the live screen's picture in main camera, a camera elsewhere
    wanted = b"program_" if mode == "main_camera" else b"live_red"
    cmds = {pid: Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") for pid in pids}
    victim = next(pid for pid, cmd in cmds.items() if any(wanted in part for part in cmd))
    victim_cmd = cmds[victim]
    os.kill(victim, signal.SIGKILL)
    time.sleep(3)
    stopped = stop(h, sid)
    report = stopped.get("capture_report") or []
    assert h.proc.poll() is None, "the host went down"
    record = mode_record(h, sid, joined=True)
    if mode == "camcorder":
        named = [r for r in report if r.get("failed") or r.get("error")]
    else:
        reports = [s.get("report") or {} for s in record.get("sound") or []]
        reports += [s.get("report") or {} for s in (record.get("program") or {}).get("segments", [])]
        named = [r for r in reports if r.get("failed") or r.get("warnings") or r.get("error")]
    assert named, f"no camera is named as having failed: {report or record}"
    if mode == "main_camera":
        assembly = record["assembly"]
        take_seconds = record["stopped_at"]
        assert assembly["state"] == "complete", assembly
        # the program covers the whole take: black where the dead encoder left off, and it says so
        assert abs(assembly["duration"] - take_seconds) < 0.6, (assembly["duration"], take_seconds)
        assert any("stopped" in w for w in assembly["warnings"]), assembly["warnings"]
    handed = [Path(a["file_path"]) for a in stopped.get("artifacts") or []]
    assert handed, stopped
    for f in handed:
        assert decodes(f), f"{f.name} is handed over but does not decode"
    # the killed camera's three seconds are not lost: its file was written as it went, and it is handed over
    victim_file = next(Path(part.decode()) for part in reversed(victim_cmd) if part.startswith(str(folder).encode()))
    assert victim_file.exists() and victim_file.stat().st_size > 0, f"{victim_file.name}: the killed camera lost everything"
    assert any(victim_file.stem.split(".")[0] in f.name for f in handed), (victim_file.name, [f.name for f in handed])


def test_the_next_take_records_normally_after_a_killed_encoder(rig):
    h = rig.host
    sid = "after_kill"
    start(h, sid, "camcorder", sources=["live_red"])
    time.sleep(3)
    stopped = stop(h, sid)
    assert not [r for r in stopped.get("capture_report") or [] if r.get("failed")], stopped
    files = media_files(session_dir(h, sid))
    assert files and all(decodes(f) for f in files)


def test_killing_the_host_leaves_no_encoder_running_and_the_take_comes_back_interrupted(rig):
    h = rig.host
    sid = "host_killed"
    start(h, sid, "camcorder", sources=["live_red", "live_blue"])
    folder = session_dir(h, sid)
    time.sleep(3)
    assert len(encoders_for(folder)) >= 2
    _kill_host(h)
    deadline = time.time() + 10
    while time.time() < deadline and encoders_for(folder):
        time.sleep(0.5)
    orphans = encoders_for(folder)
    for pid in orphans:                                     # clean up before failing, so the rig is not left dirty
        os.kill(pid, signal.SIGKILL)
    assert not orphans, f"{len(orphans)} encoder(s) kept running after the host was killed"
    sizes = {f.name: f.stat().st_size for f in media_files(folder)}
    h2 = _start(rig.work, rig.password, first=False)
    rig.host = h2
    for camera in CAMERAS:
        register(h2, camera, f"udp://{CAMERAS[camera][0]}:5004")
    listed = h2.client.get("/api/recording/sessions")
    assert listed.status_code == 200, listed.text
    body = next((s for s in listed.json() if s["session_id"] == sid), None)
    assert body is not None, [s["session_id"] for s in listed.json()]
    assert body["state"] == "stopped" and (body.get("recovery") or {}).get("interrupted"), body
    assert sizes and all(sizes.values()), f"the cameras lost what they recorded before the crash: {sizes}"
    for f in media_files(folder):
        assert decodes(f), f"{f.name} survived the crash but does not decode"


def test_a_disk_that_fills_mid_take_ends_the_take_cleanly_and_keeps_what_was_written(rig):
    """Data folder on a small tmpfs. The take starts with room for it (the gate lets it roll), then a filler file
    takes the rest of the disk, the way another program would."""
    import secrets
    disk = rig.work / "smalldisk"
    disk.mkdir()
    if subprocess.run(["mount", "-t", "tmpfs", "-o", "size=420m", "tmpfs", str(disk)], capture_output=True).returncode:
        pytest.skip("cannot mount a tmpfs here")
    h = None
    try:
        (disk / "assets").mkdir()
        password = secrets.token_urlsafe(20)
        h = _start(disk, password, first=True)
        register(h, "live_red", f"udp://{CAMERAS['live_red'][0]}:5004")
        sid = "disk_fills"
        start(h, sid, "camcorder", sources=["live_red"])
        folder = session_dir(h, sid)
        time.sleep(2)
        free = os.statvfs(disk).f_bavail * os.statvfs(disk).f_frsize
        with open(disk / "filler.bin", "wb") as f:        # leave about 1 MB
            remaining = free - 1024 * 1024
            block = b"\0" * (4 * 1024 * 1024)
            while remaining > 0:
                n = min(len(block), remaining)
                try:
                    f.write(block[:n])
                except OSError:
                    break
                remaining -= n
        time.sleep(5)
        assert h.proc.poll() is None, "the host went down when the disk filled"
        r = h.client.post(f"/api/recording/{sid}/stop")
        assert h.proc.poll() is None, "the host went down when the take was stopped on a full disk"
        # A full disk cannot take the take's closing writes: the stop says so and keeps every file for a retry.
        assert r.status_code == 409 and "No space left" in r.text and "retry" in r.text, r.text
        # While it is full, the gate refuses a new take with the reason.
        refused = h.client.post("/api/recording/start", json={"mode": "camcorder", "profile_id": PROFILE,
                                                              "countdown_seconds": 0, "sources": ["live_red"]})
        assert refused.status_code == 409 and "disk" in refused.text, refused.text
        (disk / "filler.bin").unlink()
        # With room again, stopping again finishes the take, and what was written before the disk filled plays.
        retried = stop(h, sid)
        handed = [Path(a["file_path"]) for a in retried.get("artifacts") or []]
        assert handed, retried
        for f in handed:
            assert playable_seconds(f) > 1.0, f"{f.name}: nothing written before the disk filled can be played"
        start(h, "after_disk", "camcorder", sources=["live_red"])
        time.sleep(2)
        again = stop(h, "after_disk")
        files = [Path(a["file_path"]) for a in again.get("artifacts") or []]
        assert files and all(decodes(f) for f in files), again
    finally:
        if h is not None and h.proc.poll() is None:
            _stop(h)
        subprocess.run(["umount", "-l", str(disk)], capture_output=True)
