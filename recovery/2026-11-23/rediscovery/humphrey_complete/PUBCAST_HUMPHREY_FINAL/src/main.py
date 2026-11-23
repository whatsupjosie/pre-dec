from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTasks
from starlette.websockets import WebSocketState
import uvicorn
import os
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from modules.hub import Hub
from modules.cameras import AdvancedCameraManager, CameraSource, CameraStatus, CameraMetrics
from modules.audio_job_manager import AudioJobManager
from modules.persistence import ensure_dirs, read_json, write_json, append_jsonl, sanitize_filename, allowed_upload_extension
from modules.models import ProductionState, UserState

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="PubCast Ready")

# Basic CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static mount
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Templates (not heavily used; index served via route)
templates = Jinja2Templates(directory=str(STATIC_DIR))

# In-memory Hub (connections/presence); persistent data is in /data
hub = Hub(DATA_DIR)

# Ensure required dirs/files exist at startup
ensure_dirs(DATA_DIR, ASSETS_DIR)

# ---------------- Utilities ----------------
def _get_or_set_user_id(request: Request, response: Response) -> str:
    uid = request.cookies.get("pubcast_uid")
    if not uid:
        uid = str(uuid.uuid4())
        # Minimal user bootstrap if new
        user_file = DATA_DIR / "users" / f"{uid}.json"
        if not user_file.exists():
            default_user = UserState(user_id=uid, display_name="New User").dict()
            write_json(user_file, default_user)
        # set cookie
        response.set_cookie("pubcast_uid", uid, max_age=60*60*24*365)  # 1 year
    return uid

# ---------------- Routes ----------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Simple index page with navigation to rooms
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PubCast AI</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background: #1a1a1a; 
                color: white; 
                text-align: center; 
                padding: 50px; 
            }
            .nav-btn { 
                display: inline-block; 
                padding: 15px 30px; 
                margin: 10px; 
                background: #4a6f4a; 
                color: white; 
                text-decoration: none; 
                border-radius: 5px; 
                font-size: 18px;
            }
            .nav-btn:hover { background: #5a7f5a; }
        </style>
    </head>
    <body>
        <h1>🎬 PubCast AI</h1>
        <h2>Virtual Broadcasting Studio</h2>
        <p>Choose your destination:</p>
        <div>
            <a href="/dressing" class="nav-btn">🎭 Dressing Room</a><br>
            <a href="/greenroom" class="nav-btn">🚪 Green Room</a><br>
            <a href="/control-room" class="nav-btn">📹 Control Room</a>
        </div>
        <p style="margin-top: 40px; color: #888;">
            API Status: 
            <span id="api-status">Checking...</span>
        </p>
        
        <script>
            // Test API connectivity
            fetch('/api/me')
                .then(response => response.ok ? 'Connected' : 'Error')
                .then(status => document.getElementById('api-status').textContent = status)
                .catch(() => document.getElementById('api-status').textContent = 'Offline');
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/me")
async def get_me(request: Request, response: Response):
    uid = _get_or_set_user_id(request, response)
    f = DATA_DIR / "users" / f"{uid}.json"
    data = read_json(f) if f.exists() else {"user_id": uid, "display_name": "New User"}
    return JSONResponse(data)

@app.post("/api/state/user")
async def save_user_state(request: Request, response: Response, payload: Dict[str, Any]):
    uid = _get_or_set_user_id(request, response)
    user_file = DATA_DIR / "users" / f"{uid}.json"
    current = read_json(user_file) if user_file.exists() else {}
    current.update(payload or {})
    write_json(user_file, current)
    # Broadcast presence update if display name changed
    await hub.broadcast_presence_update(uid, current.get("display_name", "User"))
    return {"ok": True}

@app.get("/api/state/user")
async def read_user_state(request: Request, response: Response):
    uid = _get_or_set_user_id(request, response)
    user_file = DATA_DIR / "users" / f"{uid}.json"
    data = read_json(user_file) if user_file.exists() else {"user_id": uid, "display_name": "New User"}
    return data

@app.get("/api/state/production")
async def get_production_state():
    return hub.get_production_state()

@app.post("/api/state/production")
async def set_production_state(payload: Dict[str, Any]):
    # validate/merge via model
    updated = hub.update_production_state(payload)
    # notify all rooms
    await hub.broadcast_system_event({"type": "production_state", "payload": updated})
    return {"ok": True, "state": updated}

# Initialize camera manager
camera_manager = AdvancedCameraManager()
# Debug print to check available methods
print(f"Camera Manager Methods: {dir(camera_manager)}")

@app.get("/api/cameras")
def list_cameras():
    """Retrieve all camera sources with detailed information"""
    cameras = camera_manager.list_cameras()
    return [
        {
            "source_id": cam.source_id,
            "name": cam.name,
            "description": cam.description,
            "location": cam.location,
            "transport": cam.transport,
            "endpoint": cam.endpoint,
            "status": cam.status,
            "input_slot": cam.input_slot,
            "metrics": {
                "latency_ms": cam.metrics.latency_ms,
                "frame_rate": cam.metrics.frame_rate,
                "resolution": cam.metrics.resolution,
                "signal_strength": cam.metrics.signal_strength,
                "last_connection": cam.metrics.last_connection,
                "connection_attempts": cam.metrics.connection_attempts
            },
            "tags": cam.tags
        }
        for cam in cameras
    ]

@app.get("/api/cameras/sources")
def get_camera_sources():
    """List camera sources (alternative endpoint)"""
    cameras = camera_manager.list_cameras()
    return {"cameras": [
        {
            "source_id": cam.source_id,
            "name": cam.name,
            "description": cam.description,
            "location": cam.location,
            "transport": cam.transport,
            "endpoint": cam.endpoint,
            "status": cam.status,
            "input_slot": cam.input_slot
        }
        for cam in cameras
    ]}

@app.get("/api/cameras/status")
def get_camera_status():
    """Get current camera system status"""
    cameras = camera_manager.list_cameras()
    online_count = len([cam for cam in cameras if cam.status == 'online'])
    
    return {
        "total_cameras": len(cameras),
        "online_cameras": online_count,
        "offline_cameras": len(cameras) - online_count,
        "system_status": "operational" if online_count > 0 else "offline"
    }

@app.post("/api/cameras")
async def add_camera(camera: Dict[str, Any]):
    """Add a new camera source"""
    try:
        # Convert dictionary to CameraSource
        camera_source = CameraSource(
            source_id=camera.get("source_id", str(uuid.uuid4())),
            name=camera.get("name", "Unnamed Camera"),
            location=camera.get("location", "unknown"),
            description=camera.get("description", ""),
            transport=camera.get("transport", CameraTransport.RTMP),
            endpoint=camera.get("endpoint", ""),
            input_slot=camera.get("input_slot", 1),
            tags=camera.get("tags", []),
            status=camera.get("status", CameraStatus.OFFLINE),
            metrics=CameraMetrics(**camera.get("metrics", {})),
            config=camera.get("config", {})
        )
        camera_manager.register(camera_source)
        return {"ok": True, "message": f"Camera {camera_source.source_id} added successfully"}
    except Exception as e:
        return JSONResponse(
            {"ok": False, "error": str(e)}, 
            status_code=400
        )

@app.post("/api/audio/patch")
async def audio_patch(payload: Dict[str, Any]):
    """
    Process audio patch request
    This is a placeholder implementation that simulates audio processing
    """
    try:
        # Simulate audio patch processing
        source = payload.get('source')
        preset = payload.get('preset')
        start_ms = payload.get('start_ms', 0)
        end_ms = payload.get('end_ms')

        # Log the patch job
        job_id = str(uuid.uuid4())
        job_log_path = DATA_DIR / "logs" / "audio_jobs.jsonl"
        job_entry = {
            "job_id": job_id,
            "status": "processing",
            "source": source,
            "preset": preset,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "timestamp": time.time()
        }
        
        # Append job log
        append_jsonl(job_log_path, job_entry)

        return {
            "ok": True, 
            "status": "processing", 
            "job_id": job_id
        }
    except Exception as e:
        return JSONResponse(
            {"ok": False, "error": str(e)}, 
            status_code=400
        )

@app.get("/api/audio/jobs")
async def list_audio_jobs(limit: int = 10):
    """List recent audio processing jobs"""
    try:
        job_log_path = DATA_DIR / "logs" / "audio_jobs.jsonl"
        
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(job_log_path), exist_ok=True)
        
        # If file does not exist, create an empty jsonl file
        if not os.path.exists(job_log_path):
            open(job_log_path, "w").close()
        
        # Read and parse jobs
        with open(job_log_path, "r") as f:
            jobs = [json.loads(line) for line in f.readlines()][-limit:]
        
        return {"ok": True, "jobs": jobs}
    except Exception as e:
        return JSONResponse(
            {"ok": False, "error": str(e)}, 
            status_code=500
        )

@app.get("/api/audio/job/{job_id}")
async def get_audio_job_status(job_id: str):
    """Retrieve status of a specific audio processing job"""
    try:
        job_log_path = DATA_DIR / "logs" / "audio_jobs.jsonl"
        
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(job_log_path), exist_ok=True)
        
        # If file does not exist, create an empty jsonl file
        if not os.path.exists(job_log_path):
            open(job_log_path, "w").close()
        
        with open(job_log_path, "r") as f:
            for line in f:
                job = json.loads(line)
                if job['job_id'] == job_id:
                    return {"ok": True, "job": job}
        
        return JSONResponse(
            {"ok": False, "error": "Job not found"}, 
            status_code=404
        )
    except Exception as e:
        return JSONResponse(
            {"ok": False, "error": str(e)}, 
            status_code=500
        )

@app.post("/api/upload")
async def upload_file(request: Request, response: Response, file: UploadFile = File(...), target: Optional[str] = Form(None)):
    uid = _get_or_set_user_id(request, response)
    filename = sanitize_filename(file.filename)
    if not allowed_upload_extension(filename):
        return JSONResponse({"ok": False, "error": "Unsupported file type."}, status_code=400)
    content = await file.read()
    max_size = 5 * 1024 * 1024  # 5 MB
    if len(content) > max_size:
        return JSONResponse({"ok": False, "error": "File too large (limit 5MB)."}, status_code=400)

    # Determine destination
    if target == "vod":
        dst_dir = ASSETS_DIR / "vod"
    else:
        dst_dir = ASSETS_DIR / "uploads" / uid
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_path = dst_dir / filename

    with open(dst_path, "wb") as f:
        f.write(content)

    return {"ok": True, "path": str(dst_path.relative_to(BASE_DIR)).replace("\\", "/")}

# ---------------- Room Navigation Routes ----------------
@app.get("/dressing", response_class=HTMLResponse)
async def dressing_room(request: Request):
    """Dressing Room - Vintage typewriter interface"""
    return FileResponse(str(STATIC_DIR / "dressing.html"))

@app.get("/greenroom", response_class=HTMLResponse) 
async def green_room(request: Request):
    """Green Room - Hallway connector between dressing and control rooms"""
    return FileResponse(str(STATIC_DIR / "greenroom.html"))

@app.get("/control-room", response_class=HTMLResponse)
async def control_room_standalone(request: Request):
    """Control Room - Standalone version (integrates with existing control.html)"""
    return FileResponse(str(STATIC_DIR / "control.html"))

# ---------------- Typewriter API Endpoints (Dressing Room) ----------------
@app.post("/api/documents/save")
async def save_typewriter_document(
    title: str = Form(...),
    content: str = Form(...),
    category: str = Form("general"),
    user_id: str = Form("default_user")
):
    """Save document from the typewriter in dressing room"""
    doc_id = str(uuid.uuid4())
    timestamp = str(int(time.time()))
    
    document = {
        "id": doc_id,
        "title": title,
        "content": content,
        "category": category,
        "userId": user_id,
        "created": timestamp,
        "modified": timestamp
    }
    
    # Save to documents directory
    doc_file = DATA_DIR / "documents" / f"{doc_id}.json"
    doc_file.parent.mkdir(exist_ok=True)
    
    with open(doc_file, 'w') as f:
        json.dump(document, f, indent=2)
    
    return {"success": True, "id": doc_id, "message": f"Document '{title}' saved successfully"}

@app.get("/api/documents/{doc_id}")
async def get_typewriter_document(doc_id: str):
    """Load a specific document for the typewriter"""
    doc_file = DATA_DIR / "documents" / f"{doc_id}.json"
    
    if not doc_file.exists():
        return JSONResponse(status_code=404, content={"error": "Document not found"})
    
    with open(doc_file, 'r') as f:
        document = json.load(f)
    
    return document

@app.get("/api/documents")
async def list_typewriter_documents(userId: str = "default_user", category: Optional[str] = None):
    """List documents for the typewriter interface"""
    docs_dir = DATA_DIR / "documents"
    docs_dir.mkdir(exist_ok=True)
    
    documents = []
    for doc_file in docs_dir.glob("*.json"):
        try:
            with open(doc_file, 'r') as f:
                doc = json.load(f)
            
            # Filter by user and category
            if doc.get("userId") == userId:
                if category is None or doc.get("category") == category:
                    documents.append(doc)
        except:
            continue  # Skip invalid files
    
    # Sort by modified time (newest first)
    documents.sort(key=lambda d: d.get("modified", "0"), reverse=True)
    
    return {"documents": documents}

# ---------------- WebSockets ----------------
@app.websocket("/ws/{room}")
async def websocket_endpoint(ws: WebSocket, room: str):
    await hub.connect(ws, room)
    try:
        while True:
            msg = await ws.receive_text()
            await hub.handle_message(ws, room, msg)
    except WebSocketDisconnect:
        await hub.disconnect(ws, room)
    except Exception:
        # defensively close
        if ws.application_state == WebSocketState.CONNECTED:
            await ws.close(code=1011)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
