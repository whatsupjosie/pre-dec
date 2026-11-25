
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webm", ".mp4", ".pdf", ".txt", ".md", ".csv", ".ppt", ".pptx"}

def ensure_dirs(data_dir: Path, assets_dir: Path):
    (data_dir / "users").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "global").mkdir(parents=True, exist_ok=True)
    (assets_dir / "vod").mkdir(parents=True, exist_ok=True)
    (assets_dir / "uploads").mkdir(parents=True, exist_ok=True)

def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def append_jsonl(path: Path, obj: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def sanitize_filename(name: str) -> str:
    # remove path parts and suspicious chars
    name = name.strip().replace("\\", "/").split("/")[-1]
    # allow alphanum, dash, underscore, dot
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name

def allowed_upload_extension(name: str) -> bool:
    ext = "." + name.split(".")[-1].lower() if "." in name else ""
    return ext in ALLOWED_EXTS
