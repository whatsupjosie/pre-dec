#!/usr/bin/env python3
"""
PubCast AI v7.0 - Main Application
===================================
The unified virtual production platform

"Feic Mo Chroí" (See My Heart) - Technology serving human storytelling

Architecture:
    Studio Control Room → Pete Enhanced → Twin Engine (Python + Rust) → WebRTC Stream
                ↓              ↓
         Voxel System    Avatar System
         
This is the entry point that coordinates all systems.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# FastAPI and WebSocket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Environment and configuration
from dotenv import load_load_dotenv()

# Core PubCast modules
from modules.hub import Hub
from modules.studio_control import StudioControl
from modules.studio_websocket import create_studio_websocket_endpoint
from modules.voxel_asset_manager import VoxelAssetManager
from modules.voxel_studio_integration import VoxelStudioIntegration
from modules.avatar_system import load_avatar_async, save_avatar_async, list_presets
from modules.bots import BotManager
from modules.recording import RecordingManager

# Pete Enhanced - The orchestrator
from pete_enhanced import PeteEnhanced

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/pubcast.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("pubcast.main")

# Load environment variables
load_dotenv()

# Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LOG_DIR = Path("./logs")

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
(DATA_DIR / "avatars").mkdir(exist_ok=True)
(DATA_DIR / "scenes").mkdir(exist_ok=True)
(DATA_DIR / "emergency_saves").mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# FASTAPI APPLICATION
# ─────────────────────────────────────────────

app = FastAPI(
    title="PubCast AI v7.0",
    description="Professional Virtual Production Platform",
    version="7.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────

# Core systems
hub: Optional[Hub] = None
pete: Optional[PeteEnhanced] = None
studio_control: Optional[StudioControl] = None
voxel_manager: Optional[VoxelAssetManager] = None
voxel_integration: Optional[VoxelStudioIntegration] = None
bot_manager: Optional[BotManager] = None
recording_manager: Optional[RecordingManager] = None

# WebSocket handlers
studio_ws_handler = None


# ─────────────────────────────────────────────
# STARTUP / SHUTDOWN
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize all systems on startup"""
    global hub, pete, studio_control, voxel_manager, voxel_integration
    global bot_manager, recording_manager, studio_ws_handler
    
    logger.info("=" * 60)
    logger.info("🎭 PubCast AI v7.0 - Starting Up")
    logger.info("=" * 60)
    
    try:
        # 1. Initialize Hub (WebSocket communication manager)
        logger.info("📡 Initializing Hub...")
        hub = Hub(data_dir=DATA_DIR)
        await hub.start()
        logger.info("✅ Hub initialized")
        
        # 2. Initialize Pete Enhanced (The Orchestrator)
        logger.info("🎭 Initializing Pete Enhanced...")
        pete = PeteEnhanced(
            hub=hub,
            data_dir=DATA_DIR,
            config={
                "rust_engine_host": os.getenv("RUST_ENGINE_HOST", "localhost"),
                "rust_engine_port": int(os.getenv("RUST_ENGINE_PORT", "9000")),
                "webrtc_stream_url": os.getenv("WEBRTC_STREAM_URL", "ws://localhost:8001/stream"),
                "enable_adaptive_quality": True,
                "enable_voice_cues": os.getenv("ENABLE_VOICE_CUES", "true").lower() == "true"
            }
        )
        
        # Initialize Pete's twin engine system
        success = await pete.initialize_twin_engine_system()
        if success:
            logger.info("✅ Pete Enhanced initialized - Twin engine operational")
        else:
            logger.warning("⚠️ Pete Enhanced initialized with limited functionality")
        
        # 3. Initialize Studio Control Room
        logger.info("🎛️ Initializing Studio Control Room...")
        studio_control = StudioControl(
            hub=hub,
            pete=pete,
            data_dir=DATA_DIR,
            config={
                "dead_man_switch_interval": float(os.getenv("DEAD_MAN_SWITCH_INTERVAL", "60.0")),
                "audio_update_interval": float(os.getenv("AUDIO_UPDATE_INTERVAL", "0.1")),
                "enable_voice_cues": os.getenv("ENABLE_VOICE_CUES", "true").lower() == "true",
                "countdown_voice": os.getenv("COUNTDOWN_VOICE", "pete")
            }
        )
        
        # Create WebSocket handler
        studio_ws_handler = create_studio_websocket_endpoint(studio_control)
        logger.info("✅ Studio Control Room initialized")
        
        # 4. Initialize Voxel Asset System
        logger.info("🎨 Initializing Voxel Asset System...")
        voxel_library_path = Path(os.getenv("VOXEL_LIBRARY_PATH", "./data/voxel_asset_library.json"))
        
        voxel_manager = VoxelAssetManager(
            library_path=voxel_library_path,
            pete=pete,
            config={
                "max_instances": int(os.getenv("MAX_SCENE_INSTANCES", "1000")),
                "max_memory_mb": int(os.getenv("MAX_SCENE_MEMORY_MB", "512"))
            }
        )
        
        # Create integration between voxel system and studio control
        voxel_integration = VoxelStudioIntegration(
            asset_manager=voxel_manager,
            studio_control=studio_control,
            pete=pete
        )
        
        # Register preflight hooks
        await voxel_integration.register_preflight_hooks()
        logger.info("✅ Voxel Asset System initialized")
        
        # 5. Initialize Bot Manager (Ollama-powered)
        logger.info("🤖 Initializing Bot Manager...")
        bot_manager = BotManager(
            hub=hub,
            data_dir=DATA_DIR,
            provider=os.getenv("BOT_PROVIDER", "ollama")
        )
        await bot_manager.start()
        logger.info("✅ Bot Manager initialized")
        
        # 6. Initialize Recording Manager
        logger.info("📼 Initializing Recording Manager...")
        recording_manager = RecordingManager(
            data_dir=DATA_DIR,
            studio_control=studio_control
        )
        logger.info("✅ Recording Manager initialized")
        
        # 7. Link Pete to Studio Control state changes
        pete.studio_control = studio_control
        
        # 8. Load default scene (Detective Office)
        logger.info("🕵️ Loading default scene...")
        default_scene = voxel_manager.create_preset_scene_detective_office()
        voxel_manager.set_active_scene(default_scene.scene_id)
        logger.info(f"✅ Default scene loaded: {default_scene.name}")
        
        logger.info("=" * 60)
        logger.info("🎭 PubCast AI v7.0 - Startup Complete")
        logger.info("=" * 60)
        logger.info(f"🌐 Studio Control Room: http://{HOST}:{PORT}/studio")
        logger.info(f"🎨 Scene Builder: http://{HOST}:{PORT}/scene-builder")
        logger.info(f"🚀 Main Launcher: http://{HOST}:{PORT}/")
        logger.info(f"📚 API Docs: http://{HOST}:{PORT}/docs")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.critical(f"💥 Startup failed: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 PubCast AI shutting down...")
    
    try:
        if pete:
            await pete.shutdown()
        if bot_manager:
            await bot_manager.stop()
        if hub:
            await hub.stop()
        
        logger.info("✅ Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


# ─────────────────────────────────────────────
# WEBSOCKET ENDPOINTS
# ─────────────────────────────────────────────

@app.websocket("/ws/studio")
async def websocket_studio(websocket: WebSocket):
    """Studio Control Room WebSocket"""
    if not studio_ws_handler:
        await websocket.close(code=1011, reason="Studio Control not initialized")
        return
    
    await studio_ws_handler.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await studio_ws_handler.handle_message(websocket, data)
    except WebSocketDisconnect:
        await studio_ws_handler.disconnect(websocket)


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Bot chat WebSocket"""
    await websocket.accept()
    
    user_id = websocket.query_params.get("user_id", "guest")
    
    if not bot_manager:
        await websocket.send_json({"error": "Bot manager not initialized"})
        await websocket.close()
        return
    
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            bot_id = data.get("bot_id", "pete")
            
            # Get bot response
            response = await bot_manager.get_bot_response(bot_id, message, user_id)
            
            await websocket.send_json({
                "bot_id": bot_id,
                "message": response,
                "timestamp": time.time()
            })
            
    except WebSocketDisconnect:
        logger.info(f"Chat WebSocket disconnected: {user_id}")


# ─────────────────────────────────────────────
# HTML INTERFACES
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_main_launcher():
    """Main PubCast Launcher"""
    html_path = Path("static/pubcast_launcher.html")
    if html_path.exists():
        with open(html_path) as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>PubCast AI v7.0</h1><p>Launcher not found</p>", status_code=404)


@app.get("/studio", response_class=HTMLResponse)
async def get_studio_control_room():
    """Studio Control Room Interface"""
    html_path = Path("static/studio_control_room.html")
    if html_path.exists():
        with open(html_path) as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Studio Control Room</h1><p>Not found</p>", status_code=404)


@app.get("/scene-builder", response_class=HTMLResponse)
async def get_scene_builder():
    """Voxel Scene Builder Interface"""
    html_path = Path("static/voxel_scene_builder.html")
    if html_path.exists():
        with open(html_path) as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Scene Builder</h1><p>Not found</p>", status_code=404)


# ─────────────────────────────────────────────
# REST API ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/api/status")
async def get_system_status():
    """Get complete system status"""
    return JSONResponse({
        "version": "7.0.0",
        "pete_status": pete.get_status() if pete else "offline",
        "studio_control": studio_control.get_status_summary() if studio_control else {},
        "voxel_system": voxel_manager.get_performance_stats() if voxel_manager else {},
        "active_scene": voxel_manager.get_active_scene().to_dict() if voxel_manager and voxel_manager.get_active_scene() else None,
        "bot_manager": bot_manager.get_status() if bot_manager else "offline"
    })


@app.get("/api/avatars/presets")
async def get_avatar_presets():
    """Get available avatar presets"""
    presets = list_presets()
    return JSONResponse([
        {
            "preset_id": p.preset_id,
            "name": p.name,
            "description": p.description
        }
        for p in presets
    ])


@app.get("/api/avatars/{user_id}")
async def get_user_avatar(user_id: str):
    """Get user's avatar state"""
    avatar = await load_avatar_async(DATA_DIR, user_id)
    return JSONResponse(avatar.dict())


@app.post("/api/avatars/{user_id}")
async def update_user_avatar(user_id: str, request: Request):
    """Update user's avatar"""
    update_data = await request.json()
    avatar = await save_avatar_async(DATA_DIR, user_id, update_data)
    return JSONResponse(avatar.dict())


@app.get("/api/scenes")
async def list_scenes():
    """List all available scenes"""
    if not voxel_manager:
        return JSONResponse({"error": "Voxel manager not initialized"}, status_code=503)
    
    scenes = []
    scenes_dir = DATA_DIR / "scenes"
    if scenes_dir.exists():
        for scene_file in scenes_dir.glob("*.json"):
            scene = voxel_manager.load_scene_from_file(scene_file)
            if scene:
                scenes.append({
                    "scene_id": scene.scene_id,
                    "name": scene.name,
                    "description": scene.description,
                    "instance_count": len(scene.instances),
                    "asset_count": len(scene.required_assets)
                })
    
    return JSONResponse(scenes)


@app.post("/api/scenes/{scene_id}/activate")
async def activate_scene(scene_id: str):
    """Set a scene as active"""
    if not voxel_manager:
        return JSONResponse({"error": "Voxel manager not initialized"}, status_code=503)
    
    success = voxel_manager.set_active_scene(scene_id)
    if success:
        return JSONResponse({"status": "success", "active_scene": scene_id})
    return JSONResponse({"error": "Scene not found"}, status_code=404)


@app.get("/api/assets")
async def list_assets():
    """Get complete asset library"""
    if not voxel_manager:
        return JSONResponse({"error": "Voxel manager not initialized"}, status_code=503)
    
    assets = voxel_manager.get_all_assets()
    return JSONResponse([asset.to_dict() for asset in assets])


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "version": "7.0.0",
        "systems": {
            "hub": hub is not None,
            "pete": pete is not None,
            "studio_control": studio_control is not None,
            "voxel_manager": voxel_manager is not None,
            "bot_manager": bot_manager is not None
        }
    })


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def main():
    """Main entry point"""
    logger.info("🎭 Starting PubCast AI v7.0...")
    
    # Run server
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,  # Disable reload in production
        log_level="info"
    )


if __name__ == "__main__":
    main()
