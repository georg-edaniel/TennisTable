"""WebSocket connection manager — broadcast to all or per-session rooms."""
import json
import asyncio
from fastapi import WebSocket
from typing import Dict, Set


class WebSocketManager:
    def __init__(self):
        # All active connections
        self._connections: Set[WebSocket] = set()
        # session-scoped rooms: session_id → set of WebSockets
        self._rooms: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)
            for room in self._rooms.values():
                room.discard(ws)

    async def join_room(self, ws: WebSocket, session_id: int):
        async with self._lock:
            self._rooms.setdefault(session_id, set()).add(ws)

    async def leave_room(self, ws: WebSocket, session_id: int):
        async with self._lock:
            if session_id in self._rooms:
                self._rooms[session_id].discard(ws)

    async def broadcast_all(self, message: dict):
        """Send to every connected WebSocket."""
        data = json.dumps(message)
        dead = set()
        async with self._lock:
            connections = set(self._connections)
        for ws in connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._connections -= dead

    async def broadcast_room(self, session_id: int, message: dict):
        """Send only to WebSockets in a specific session room."""
        data = json.dumps(message)
        dead = set()
        async with self._lock:
            room = set(self._rooms.get(session_id, set()))
        for ws in room:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                if session_id in self._rooms:
                    self._rooms[session_id] -= dead
