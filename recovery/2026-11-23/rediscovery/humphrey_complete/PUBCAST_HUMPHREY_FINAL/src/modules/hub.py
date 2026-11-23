
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, Set, List
from fastapi import WebSocket
from starlette.websockets import WebSocketState
from modules.persistence import read_json, write_json, append_jsonl
from modules.models import ProductionState

class Hub:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.user_display_name: Dict[str, str] = {}  # uid -> display name (optional; for presence)
        # production state on disk
        self.prod_file = self.data_dir / "global" / "production.json"
        if not self.prod_file.parent.exists():
            self.prod_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.prod_file.exists():
            write_json(self.prod_file, ProductionState().dict())

    def get_production_state(self) -> Dict[str, Any]:
        return read_json(self.prod_file)

    def update_production_state(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_production_state()
        # merge shallowly
        current.update(patch or {})
        # validate through model
        model = ProductionState(**current)
        write_json(self.prod_file, model.dict())
        return model.dict()

    async def connect(self, ws: WebSocket, room: str):
        await ws.accept()
        self.rooms.setdefault(room, set()).add(ws)
        # send recent history
        history_path = self._log_path(room)
        last_msgs: List[str] = []
        if history_path.exists():
            # send last 50 lines
            with open(history_path, "r", encoding="utf-8") as f:
                last_msgs = f.readlines()[-50:]
        if last_msgs:
            await ws.send_text(json.dumps({"type": "history", "payload": [json.loads(l) for l in last_msgs]}))
        # announce presence
        await self._broadcast(room, {"type": "presence", "payload": {"room": room, "count": len(self.rooms.get(room, []))}})

    async def disconnect(self, ws: WebSocket, room: str):
        try:
            self.rooms.get(room, set()).discard(ws)
        finally:
            await self._broadcast(room, {"type": "presence", "payload": {"room": room, "count": len(self.rooms.get(room, []))}})
            if ws.application_state == WebSocketState.CONNECTED:
                await ws.close()

    async def broadcast_system_event(self, event: Dict[str, Any]):
        for room, conns in self.rooms.items():
            await self._broadcast(room, event)

    async def broadcast_presence_update(self, user_id: str, display_name: str):
        # Could be extended to map sockets to user ids to show names; minimal for now
        self.user_display_name[user_id] = display_name
        await self.broadcast_system_event({"type": "user_update", "payload": {"user_id": user_id, "display_name": display_name}})

    async def handle_message(self, ws: WebSocket, room: str, raw: str):
        # Expect raw to be JSON string
        try:
            data = json.loads(raw)
        except Exception:
            return
        typ = data.get("type")
        if typ == "chat":
            payload = {
                "t": time.time(),
                "room": room,
                "user": data.get("user", "anon"),
                "text": data.get("text", ""),
            }
            append_jsonl(self._log_path(room), payload)
            await self._broadcast(room, {"type": "chat", "payload": payload})
        elif typ == "signal":
            # extension point for invites / cues
            await self._broadcast(room, {"type": "signal", "payload": data.get("payload", {})})
        elif typ == "production_state":
            # allow control room to push updates via ws (UI convenience)
            updated = self.update_production_state(data.get("payload", {}))
            await self.broadcast_system_event({"type": "production_state", "payload": updated})
        else:
            # echo unknown
            await ws.send_text(json.dumps({"type": "error", "payload": {"msg": "unknown type"}}))

    async def _broadcast(self, room: str, msg: Dict[str, Any]):
        dead: List[WebSocket] = []
        for ws in list(self.rooms.get(room, set())):
            try:
                if ws.application_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(msg))
                else:
                    dead.append(ws)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.rooms.get(room, set()).discard(ws)

    def _log_path(self, room: str) -> Path:
        logs_dir = self.data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / f"{room}.jsonl"
