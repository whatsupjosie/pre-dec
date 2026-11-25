import uuid
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

class AudioJobManager:
    """
    Manages audio processing jobs with persistent tracking
    """
    def __init__(self, job_log_dir: Path):
        self.job_log_dir = job_log_dir
        self.job_log_dir.mkdir(parents=True, exist_ok=True)
        self.job_log_path = job_log_dir / "audio_jobs.jsonl"

    def create_job(self, source: str, preset: str, start_ms: int = 0, end_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Create a new audio processing job
        """
        job_id = str(uuid.uuid4())
        job_entry = {
            "job_id": job_id,
            "source": source,
            "preset": preset,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "status": "pending",
            "created_at": time.time(),
            "updated_at": time.time(),
            "progress": 0,
            "output_path": None,
            "error": None
        }

        # Append job to log file
        with open(self.job_log_path, "a") as f:
            f.write(json.dumps(job_entry) + "\n")

        return job_entry

    def update_job_status(self, job_id: str, status: str, progress: Optional[float] = None, 
                           output_path: Optional[str] = None, error: Optional[str] = None):
        """
        Update the status of an existing job
        """
        jobs = []
        updated = False

        # Read existing jobs
        with open(self.job_log_path, "r") as f:
            for line in f:
                job = json.loads(line)
                if job['job_id'] == job_id:
                    job['status'] = status
                    job['updated_at'] = time.time()
                    if progress is not None:
                        job['progress'] = progress
                    if output_path is not None:
                        job['output_path'] = output_path
                    if error is not None:
                        job['error'] = error
                    updated = True
                jobs.append(job)

        # Write updated jobs back
        if updated:
            with open(self.job_log_path, "w") as f:
                for job in jobs:
                    f.write(json.dumps(job) + "\n")

        return updated

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job status
        """
        with open(self.job_log_path, "r") as f:
            for line in f:
                job = json.loads(line)
                if job['job_id'] == job_id:
                    return job
        return None

    def list_recent_jobs(self, limit: int = 10) -> list:
        """
        List recent jobs
        """
        with open(self.job_log_path, "r") as f:
            jobs = [json.loads(line) for line in f]
            return sorted(jobs, key=lambda x: x['created_at'], reverse=True)[:limit]
