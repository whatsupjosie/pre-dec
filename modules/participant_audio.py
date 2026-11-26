"""Explicit one-way participant audio into the canonical browser program mixer.

Authenticated same-origin WebSockets relay bounded, ordered mono PCM frames.
Invitations and per-browser capabilities are ephemeral; no private-room capture.
Single application worker, matching the existing camera manager architecture.
"""
from __future__ import annotations
import asyncio
import json
from collections import deque
import secrets
import struct
import time
from dataclasses import dataclass, field
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from .auth import role_gte
from .route_security import current_identity, authorize_websocket


class Join(BaseModel):
    consent: bool


@dataclass
class Peer:
    actor: str
    key: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    seen: float = field(default_factory=time.monotonic)
    socket: WebSocket | None = None


# A guest's microphone may arrive in bursts (a network stall, a busy browser tab, a phone waking its radio). The
# relay lets a sender run ahead of real time by up to BURST_SECONDS and refills at SUSTAINED x real time, so a
# backlog catches up while a sender that keeps flooding is still cut off. (It used to cut off any guest who sent
# more than 1.2 s of audio within one second, which every catch-up after a hiccup of about a second does: one of
# the ways a guest's sound dropped out of a long recording.)
BURST_SECONDS = 5.0
SUSTAINED = 1.25
SLACK_BYTES = 32768
# Audio waiting for the director's desk. A desk that stalls loses its oldest audio, never a guest's connection.
OUTBOX_BYTES = 8 * 1024 * 1024
SEND_TIMEOUT = 5.0


class HostOutbox:
    """Everything bound for the director's desk, sent in order by one task.

    A guest's handler only queues and returns, so a desk that is slow for a moment no longer ends the guest's
    connection (it used to: a one-second send timeout inside the guest's own handler). When the desk falls more
    than OUTBOX_BYTES behind, the oldest audio frames are dropped, and the desk is told how many, per guest,
    before the next thing it receives. Control messages (a guest arrived, left) are never dropped.
    """

    def __init__(self, socket_of, *, limit: int = OUTBOX_BYTES, timeout: float = SEND_TIMEOUT):
        self._socket_of = socket_of            # returns the desk's socket, or None
        self.limit, self.timeout = limit, timeout
        self.items: deque = deque()
        self.bytes = 0
        self.dropped: dict[str, int] = {}
        self.sent = 0
        self.stalls = 0
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.closed = False

    def put(self, message) -> None:
        if self.closed:
            return
        self.items.append(message)
        if isinstance(message, bytes):
            self.bytes += len(message)
            while self.bytes > self.limit:
                if not self._drop_oldest_audio():
                    break
        self._wake.set()
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run(), name="participant-audio-desk")

    def _drop_oldest_audio(self) -> bool:
        for index, item in enumerate(self.items):
            if isinstance(item, bytes):
                del self.items[index]
                self.bytes -= len(item)
                peer = item[:16].hex()
                self.dropped[peer] = self.dropped.get(peer, 0) + 1
                return True
        return False

    async def _send(self, socket, message) -> None:
        if isinstance(message, bytes):
            await asyncio.wait_for(socket.send_bytes(message), self.timeout)
        else:
            await asyncio.wait_for(socket.send_json(message), self.timeout)

    async def _run(self) -> None:
        while not self.closed:
            if not self.items and not self.dropped:
                self._wake.clear()
                await self._wake.wait()
                continue
            socket = self._socket_of()
            if socket is None:
                return                      # the desk's own handler closes the room
            # A gap report goes just before the next audio, after any control message already queued, so the
            # desk always meets a guest ("source") before hearing about that guest's lost frames.
            if self.dropped and (not self.items or isinstance(self.items[0], bytes)):
                message, self.dropped = {"type": "gap", "dropped_frames": dict(self.dropped)}, {}
            else:
                message = self.items.popleft()
                if isinstance(message, bytes):
                    self.bytes -= len(message)
            try:
                await self._send(socket, message)
                self.sent += 1
            except asyncio.TimeoutError:
                self.stalls += 1
                if isinstance(message, bytes):
                    peer = message[:16].hex()
                    self.dropped[peer] = self.dropped.get(peer, 0) + 1
            except Exception:
                return                      # the desk went away; its handler closes the room

    async def close(self) -> None:
        self.closed = True
        self._wake.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


@dataclass
class Room:
    host: str
    peers: dict[str, Peer]
    sample_rate: int = 0
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    outbox: HostOutbox | None = None


def create_participant_audio_router(*, clock=time.monotonic):
    router = APIRouter(prefix='/api/participant-audio', tags=['Participant Audio'])
    rooms: dict[str, Room] = {}
    lease = 20

    def prune():
        for rid, room in list(rooms.items()):
            if clock() - room.peers[room.host].seen > lease:
                del rooms[rid]
            # Connected sockets manage their own receive deadlines. Unused
            # reservations expire; an abandoned invitation cannot fill the desk.
            else:
                for pid, peer in list(room.peers.items()):
                    if pid != room.host and peer.socket is None and clock() - peer.seen > lease:
                        del room.peers[pid]

    def authenticated(identity):
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to contribute production audio')

    def get_room(rid):
        prune()
        if rid not in rooms:
            raise HTTPException(404, 'Audio desk closed or invitation expired')
        return rooms[rid]

    def authorize(room, pid, key, identity):
        authenticated(identity)
        peer = room.peers.get(pid)
        if not peer or peer.actor != identity['user_id'] or not secrets.compare_digest(peer.key, key):
            raise HTTPException(404, 'Audio connection not found')
        peer.seen = clock()
        return peer

    def reservation(rid, pid, peer):
        return {'room': rid, 'peer': pid, 'key': peer.key, 'lease_seconds': lease}

    async def to_host(room, message):
        host = room.peers[room.host].socket
        if host is None:
            raise ValueError('Audio desk is not listening')
        if room.outbox is None:
            room.outbox = HostOutbox(lambda r=room: r.peers[r.host].socket if r.host in r.peers else None)
        room.outbox.put(message)

    async def close_room(rid):
        room = rooms.pop(rid, None)
        if room and room.outbox is not None:
            await room.outbox.close()
        if room:
            for peer in list(room.peers.values()):
                if peer.socket:
                    try:
                        await asyncio.wait_for(peer.socket.close(code=1000), 1)
                    except (Exception, asyncio.CancelledError):
                        pass

    @router.post('/rooms', status_code=201)
    async def open_desk(identity=Depends(current_identity)):
        authenticated(identity)
        if not role_gte(identity['role'], 'mod'):
            raise HTTPException(403, 'Director role required to receive production audio')
        prune()
        if len(rooms) >= 16:
            raise HTTPException(429, 'Audio desk capacity reached')
        rid, pid = secrets.token_urlsafe(24), secrets.token_hex(16)
        peer = Peer(str(identity['user_id']), seen=clock())
        rooms[rid] = Room(pid, {pid: peer})
        return reservation(rid, pid, peer)

    @router.post('/rooms/{rid}/peers', status_code=201)
    async def join(rid: str, body: Join, identity=Depends(current_identity)):
        authenticated(identity)
        if not body.consent:
            raise HTTPException(400, 'Consent to send and record microphone audio is required')
        room = get_room(rid)
        if not room.sample_rate or room.peers[room.host].socket is None:
            raise HTTPException(409, 'Audio desk is not ready to receive microphones')
        if len(room.peers) >= 9:
            raise HTTPException(429, 'Eight participant audio inputs are already connected')
        pid = secrets.token_hex(16)
        peer = Peer(str(identity['user_id']), seen=clock())
        room.peers[pid] = peer
        return {**reservation(rid, pid, peer), 'host': room.host, 'sample_rate': room.sample_rate}

    @router.delete('/rooms/{rid}/peers/{pid}')
    async def leave(rid: str, pid: str, x_audio_key: str = Header(default=''), identity=Depends(current_identity)):
        room = get_room(rid)
        peer = authorize(room, pid, x_audio_key, identity)
        if pid == room.host:
            await close_room(rid)
        elif peer.socket:
            await peer.socket.close(code=1000)
        else:
            del room.peers[pid]
        return {'ok': True}

    @router.websocket('/rooms/{rid}/peers/{pid}/media')
    async def media(ws: WebSocket, rid: str, pid: str):
        identity = await authorize_websocket(ws)
        if not identity or not identity.get('authenticated'):
            if identity:
                await ws.close(code=1008)
            return
        if ws.headers.get('origin') not in {f'http://{ws.headers.get("host")}', f'https://{ws.headers.get("host")}'}:
            await ws.close(code=1008, reason='Same-origin contribution required')
            return
        await ws.accept()
        room = peer = None
        try:
            hello_text = await asyncio.wait_for(ws.receive_text(), 5)
            if len(hello_text) > 2048:
                raise ValueError('Audio capability message is too large')
            hello = json.loads(hello_text)
            if not isinstance(hello, dict):
                raise ValueError('Invalid audio capability message')
            room = get_room(rid)
            peer = authorize(room, pid, str(hello.get('key', ''))[:128], identity)
            if peer.socket is not None:
                raise ValueError('This audio connection is already in use')
            rate = hello.get('sample_rate', 0)
            if type(rate) is not int or rate not in (8000,16000,22050,24000,32000,44100,48000,88200,96000,192000):
                raise ValueError('Unsupported microphone sample rate')
            if pid == room.host:
                room.sample_rate = rate
            elif rate != room.sample_rate:
                raise ValueError('Microphone clock does not match production sample rate')
            peer.socket = ws
            if pid != room.host:
                await to_host(room, {'type':'source', 'peer':pid, 'actor':peer.actor, 'sample_rate':rate})
            await ws.send_json({'ok':True})
            sequence = 0
            capacity = rate * 2 * BURST_SECONDS
            budget, refilled = capacity, clock()
            while True:
                packet = await asyncio.wait_for(ws.receive(), lease)
                if packet['type'] == 'websocket.disconnect':
                    break
                if rooms.get(rid) is not room:
                    raise ValueError('Audio desk closed')
                peer.seen = clock()
                if packet.get('text') == 'ping':
                    continue
                if pid == room.host and packet.get('text') and len(packet['text']) <= 100:
                    control = json.loads(packet['text'])
                    if not isinstance(control, dict):
                        raise ValueError('Invalid audio control message')
                    target = room.peers.get(control.get('drop'))
                    if target and target is not peer and target.socket:
                        await asyncio.wait_for(target.socket.close(code=1000), 1)
                        continue
                    raise ValueError('Invalid source disconnect')
                data = packet.get('bytes')
                if pid == room.host or not data or not 6 <= len(data) <= 16388 or (len(data)-4)%2:
                    raise ValueError('Invalid microphone frame')
                if struct.unpack_from('<I',data)[0] != sequence:
                    raise ValueError('Microphone frame sequence lost')
                sequence += 1
                now = clock()
                budget = min(capacity, budget + (now - refilled) * rate * 2 * SUSTAINED)
                refilled = now
                budget -= len(data) - 4
                if budget < -SLACK_BYTES:
                    raise ValueError('Microphone rate exceeds its bound')
                await to_host(room, bytes.fromhex(pid)+data)
        except (WebSocketDisconnect, asyncio.TimeoutError, HTTPException, ValueError, RuntimeError, KeyError, TypeError):
            pass
        finally:
            # A rejected duplicate must not remove the first connection.
            if room and peer and peer.socket is ws:
                peer.socket = None
                if pid == room.host:
                    await close_room(rid)
                else:
                    room.peers.pop(pid, None)
                    try:
                        await to_host(room, {'type':'left','peer':pid})
                    except (Exception, asyncio.CancelledError):
                        pass
            try:
                await ws.close(code=1000)
            except RuntimeError:
                pass
    return router
