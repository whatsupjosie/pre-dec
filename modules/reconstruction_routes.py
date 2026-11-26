# PubCast AI — reconstruction_routes.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""Reconstruction jobs: render a stopped take from its show data, from any camera, in the background.

One job renders at a time (it uses the whole processor); others wait in order. A finished video is
added to its take as an artifact and its manifest as a data file, so both travel with export.
A failure is kept on the job with its reason; nothing half-made is ever added to a take.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request as HTTPRequest

from modules.recording import RecordingState
from modules.reconstruction import (FPS_CHOICES, QUALITY, ReconstructionError, Request, check_camera,
                                    find_browser, reconstruct)
from modules.route_security import require_role

logger = logging.getLogger("pubcast.reconstruction_routes")

MAX_JOBS_KEPT = 200


class ReconstructionService:
    def __init__(self, recording, *, browser: Optional[Dict[str, Any]] = None):
        self.recording = recording
        self.browser = browser
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._lock: Optional[asyncio.Lock] = None

    def capabilities(self) -> Dict[str, Any]:
        browser = self.browser or find_browser()
        import shutil
        return {"browser": browser, "ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")),
                "fps": list(FPS_CHOICES), "quality": list(QUALITY), "audio": ["take", "none"],
                "cameras": ["program", "p25d_<package>_<shot>", {"center": "[x, y] 0..1", "zoom": "1..4"}]}

    def submit(self, session_id: str, request: Request, *, actor: str) -> Dict[str, Any]:
        session = self.recording.get_session(session_id)          # KeyError -> 404
        if session.state not in (RecordingState.STOPPED, RecordingState.ARCHIVED):
            raise ReconstructionError("Stop the take before reconstructing it; its show data is still being written")
        request = request.checked()
        job_id = uuid.uuid4().hex[:16]
        job = {"job_id": job_id, "session_id": session_id, "state": "queued", "actor": actor,
               "request": {"camera": request.camera, "fps": request.fps, "quality": request.quality,
                           "audio": request.audio, "label": request.label},
               "queued_utc": time.time(), "progress": None, "result": None, "error": None}
        self.jobs[job_id] = job
        self._trim()
        task = asyncio.get_running_loop().create_task(self._run(job, request), name=f"reconstruct-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t, j=job_id: self._tasks.pop(j, None))
        return dict(job)

    def _trim(self) -> None:
        finished = [j for j in self.jobs.values() if j["state"] in ("complete", "failed", "cancelled")]
        for job in sorted(finished, key=lambda j: j["queued_utc"])[:max(0, len(self.jobs) - MAX_JOBS_KEPT)]:
            self.jobs.pop(job["job_id"], None)

    async def _run(self, job: Dict[str, Any], request: Request) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if job["state"] == "cancelled":
                return
            job.update(state="rendering", started_utc=time.time())
            take_dir = self.recording._session_dir(job["session_id"])

            def progress(p: Dict[str, Any]) -> None:
                job["progress"] = p

            try:
                manifest = await reconstruct(take_dir, request, progress=progress,
                                             cancelled=lambda: job["state"] == "cancelling", browser=self.browser)
                video = take_dir / manifest["file"]
                artifact = self.recording.register_artifact(job["session_id"], video)
                self.recording.attach_data_file(job["session_id"], take_dir / f"{video.stem}.json")
                job.update(state="complete", finished_utc=time.time(),
                           result={"file": manifest["file"], "artifact": artifact.name,
                                   "manifest": f"{video.stem}.json", "frames": manifest["frames"],
                                   "duration": manifest["verification"]["ffprobe"].get("duration"),
                                   "stretches": manifest["stretches"], "render_seconds": manifest["render_seconds"]})
            except ReconstructionError as exc:
                state = "cancelled" if str(exc) == "Cancelled" else "failed"
                job.update(state=state, finished_utc=time.time(), error=str(exc))
            except Exception as exc:              # reported on the job, never swallowed
                logger.exception("Reconstruction %s failed", job["job_id"])
                job.update(state="failed", finished_utc=time.time(), error=f"{type(exc).__name__}: {exc}")

    def cancel(self, job_id: str) -> Dict[str, Any]:
        job = self.jobs[job_id]
        if job["state"] == "queued":
            job["state"] = "cancelled"
        elif job["state"] == "rendering":
            job["state"] = "cancelling"
        return dict(job)

    async def shutdown(self) -> None:
        for job in self.jobs.values():
            if job["state"] in ("queued", "rendering"):
                job["state"] = "cancelling" if job["state"] == "rendering" else "cancelled"
        tasks = list(self._tasks.values())
        if tasks:
            await asyncio.wait(tasks, timeout=30)


def create_reconstruction_router(service: ReconstructionService) -> APIRouter:
    router = APIRouter(tags=["Reconstruction"])

    @router.get("/api/reconstruction/capabilities")
    async def capabilities(identity: Dict[str, Any] = Depends(require_role("mod"))):
        return service.capabilities()

    @router.post("/api/recording/{session_id}/reconstruct")
    async def submit(session_id: str, request: HTTPRequest, identity: Dict[str, Any] = Depends(require_role("mod"))):
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Body must be JSON") from None
        if not isinstance(body, dict) or set(body) - {"camera", "fps", "quality", "audio", "label"}:
            raise HTTPException(400, "Fields: camera, fps, quality, audio, label")
        fps = body.get("fps", 30)
        if isinstance(fps, bool) or not isinstance(fps, int):
            raise HTTPException(400, "fps must be an integer")
        try:
            req = Request(camera=check_camera(body.get("camera", "program")), fps=fps,
                          quality=str(body.get("quality", "standard")), audio=str(body.get("audio", "take")),
                          label=str(body.get("label", "")))
            return service.submit(session_id, req, actor=str(identity.get("user_id") or "operator"))
        except KeyError:
            raise HTTPException(404, "Take not found") from None
        except ReconstructionError as exc:
            raise HTTPException(409 if "Stop the take" in str(exc) else 400, str(exc)) from None

    @router.get("/api/reconstruction/jobs/{job_id}")
    async def job(job_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        if job_id not in service.jobs:
            raise HTTPException(404, "Job not found")
        return service.jobs[job_id]

    @router.post("/api/reconstruction/jobs/{job_id}/cancel")
    async def cancel(job_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        if job_id not in service.jobs:
            raise HTTPException(404, "Job not found")
        return service.cancel(job_id)

    @router.get("/api/recording/{session_id}/reconstructions")
    async def for_take(session_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {"jobs": [j for j in service.jobs.values() if j["session_id"] == session_id]}

    return router


__all__ = ["ReconstructionService", "create_reconstruction_router"]
