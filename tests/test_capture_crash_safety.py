"""Live files are written so a crash costs about a second, and encoders end with the host (unit level).

The real proofs, with FFmpeg killed and the host killed, are in tests/test_recording_faults_e2e.py.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules import child_lifetime
from modules.capture import _build_ffmpeg_output


def profile(**kw):
    base = dict(video_codec="h264", audio_codec="aac", video_bitrate="50Mbps", audio_bitrate="320kbps",
                resolution="1920x1080", frame_rate="30", is_audio_only=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_live_mp4_is_written_in_fragments_and_live_webm_closes_a_cluster_each_second():
    mp4 = _build_ffmpeg_output(profile(), Path("cam.mp4"))
    assert "+frag_keyframe+empty_moov+default_base_moof" in mp4 and mp4[mp4.index("-frag_duration") + 1] == "1000000"
    webm = _build_ffmpeg_output(profile(video_codec="vp9", audio_codec="opus"), Path("cam.webm"))
    assert webm[webm.index("-cluster_time_limit") + 1] == "1000" and "-flush_packets" in webm
    assert mp4[-1] == "cam.mp4" and webm[-1] == "cam.webm"


def test_an_offline_render_is_an_ordinary_file():
    args = _build_ffmpeg_output(profile(), Path("program.mp4"), live=False)
    assert "-movflags" not in args and "-cluster_time_limit" not in args and "-flush_packets" not in args


def test_wav_keeps_flushing_every_packet():
    args = _build_ffmpeg_output(profile(video_codec=None, audio_codec="pcm_s16le", is_audio_only=True), Path("s.wav"))
    assert "-flush_packets" in args and "-movflags" not in args


def test_a_fragmented_mp4_killed_mid_write_still_plays(tmp_path):
    """The reason for fragments, shown with FFmpeg itself: kill it, then read the file."""
    if not __import__("shutil").which("ffmpeg"):
        pytest.skip("no ffmpeg")
    out = tmp_path / "killed.mp4"
    args = _build_ffmpeg_output(profile(resolution="320x180"), out)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-re", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30",
                             "-f", "lavfi", "-i", "sine=frequency=440", *args], stderr=subprocess.DEVNULL)
    time.sleep(3)
    proc.send_signal(signal.SIGKILL)
    proc.wait()
    done = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(out), "-f", "null", "-"],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-500:]
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True)
    assert float(probe.stdout.strip()) > 1.0


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the Linux mechanism")
def test_on_linux_a_child_gets_sigterm_when_its_parent_dies(tmp_path):
    """A middle process starts a sleeper with the tie, then is killed: the sleeper must end too."""
    marker = tmp_path / "child.pid"
    code = (
        "import subprocess, sys, time\n"
        "from modules import child_lifetime\n"
        "p = subprocess.Popen(['sleep', '60'], **child_lifetime.spawn_kwargs())\n"
        f"open(r'{marker}', 'w').write(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    middle = subprocess.Popen([sys.executable, "-c", code], cwd=str(Path(__file__).resolve().parents[1]))
    deadline = time.time() + 10
    while not marker.exists() and time.time() < deadline:
        time.sleep(0.05)
    child = int(marker.read_text())
    middle.send_signal(signal.SIGKILL)
    middle.wait()
    deadline = time.time() + 5
    alive = True
    while time.time() < deadline:
        try:
            os.kill(child, 0)
            with open(f"/proc/{child}/stat") as f:
                if f.read().split()[2] == "Z":
                    alive = False
                    break
        except (ProcessLookupError, FileNotFoundError):
            alive = False
            break
        time.sleep(0.05)
    if alive:
        os.kill(child, signal.SIGKILL)
    assert not alive, "the child outlived its parent"
    assert child_lifetime.status()["encoders_end_with_host"]
