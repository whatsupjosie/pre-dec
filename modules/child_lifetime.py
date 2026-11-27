"""Encoders die with the host.

When the host process is killed (a crash, the task manager, a power-button shutdown of the app), the FFmpeg
encoders it started did not die with it. tests/test_recording_faults_e2e.py found them, 2026-11-27, still running
after the host was gone: writing into the take folder with nobody to stop them, holding the camera, and filling the
disk. Each long-running encoder is now tied to the host's life:

* Linux: the kernel sends the encoder SIGTERM when the host dies (PR_SET_PDEATHSIG). FFmpeg finishes its file on
  SIGTERM, so the take is closed properly even though the host is gone.
* Windows: each encoder joins a job object that is closed when the host's handles are, and the job is set to end
  its processes then (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE). This ends the encoder at once rather than letting it
  finish, so live files are written in crash-safe form (modules/capture.py, _CRASH_SAFE_MUXING): at most about a
  second is lost. NOT TESTED on Windows here (written for it, run only on Linux).
* macOS and others: no such mechanism is used; ``status()`` says so.

Nothing here is required for recording to work: if the mechanism is unavailable it logs once and recording goes on
as before.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("pubcast.child_lifetime")

_PR_SET_PDEATHSIG = 1
_SIGTERM = 15
_job_handle: Optional[int] = None
_warned = False


def _linux_preexec(parent_pid: int) -> Callable[[], None]:
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)

    def tie() -> None:                     # runs in the child, between fork and exec
        libc.prctl(_PR_SET_PDEATHSIG, _SIGTERM, 0, 0, 0)
        if os.getppid() != parent_pid:     # the host died before the tie was made
            os._exit(1)
    return tie


def spawn_kwargs() -> Dict[str, Any]:
    """Extra keyword arguments for subprocess/asyncio process creation that tie the child to this process."""
    if sys.platform.startswith("linux"):
        try:
            return {"preexec_fn": _linux_preexec(os.getpid())}
        except Exception as exc:  # noqa: BLE001
            _warn(f"Linux parent-death signal unavailable: {exc}")
    return {}


def adopt(pid: int) -> bool:
    """After the child started: on Windows, put it in the job that ends with the host. True when tied."""
    if sys.platform != "win32":
        return sys.platform.startswith("linux")
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        global _job_handle
        if _job_handle is None:
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount",
                                                              "OtherOperationCount", "ReadTransferCount",
                                                              "WriteTransferCount", "OtherTransferCount")]

            class BASIC(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class EXTENDED(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            info = EXTENDED()
            info.BasicLimitInformation.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # 9: extended
                raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
            _job_handle = job
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x0100 | 0x0001, False, pid)   # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        if not handle:
            raise OSError(ctypes.get_last_error(), "OpenProcess failed")
        try:
            if not kernel32.AssignProcessToJobObject(_job_handle, handle):
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
        finally:
            kernel32.CloseHandle(handle)
        return True
    except Exception as exc:  # noqa: BLE001
        _warn(f"Windows job object unavailable: {exc}")
        return False


def status() -> Dict[str, Any]:
    if sys.platform.startswith("linux"):
        how = "parent-death signal (SIGTERM; the encoder finishes its file)"
    elif sys.platform == "win32":
        how = "job object, kill on close (the encoder ends at once; crash-safe files lose about a second)"
    else:
        how = None
    return {"platform": sys.platform, "encoders_end_with_host": how is not None, "how": how}


def _warn(message: str) -> None:
    global _warned
    if not _warned:
        logger.warning("%s; encoders may outlive the host if it is killed", message)
        _warned = True
