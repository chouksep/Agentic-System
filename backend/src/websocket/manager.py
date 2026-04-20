from fastapi import FastAPI
import socketio
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=["http://localhost:3000", "http://localhost:5173"],
    ping_timeout=60,
    ping_interval=25,
)


class ConnectionManager:
    """Manage WebSocket connections for real-time metrics."""

    def __init__(self):
        self.active_calls: Dict[str, List[str]] = {}  # call_id -> [sid1, sid2, ...]
        self.user_sessions: Dict[str, str] = {}  # user_id -> sid

    async def connect(self, call_id: str, user_id: str, sid: str):
        """Register a new connection for a call."""
        if call_id not in self.active_calls:
            self.active_calls[call_id] = []
        self.active_calls[call_id].append(sid)
        self.user_sessions[user_id] = sid
        logger.info(f"User {user_id} connected to call {call_id}")

    async def disconnect(self, call_id: str, user_id: str, sid: str):
        """Remove a connection."""
        if call_id in self.active_calls:
            self.active_calls[call_id].remove(sid)
            if not self.active_calls[call_id]:
                del self.active_calls[call_id]
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        logger.info(f"User {user_id} disconnected from call {call_id}")

    async def broadcast_to_call(self, call_id: str, event: str, data: dict):
        """Broadcast event to all users in a call."""
        if call_id in self.active_calls:
            for sid in self.active_calls[call_id]:
                await sio.emit(event, data, to=sid)
            logger.debug(f"Broadcast {event} to {len(self.active_calls[call_id])} users in call {call_id}")

    async def broadcast_to_user(self, user_id: str, event: str, data: dict):
        """Send event to specific user."""
        if user_id in self.user_sessions:
            sid = self.user_sessions[user_id]
            await sio.emit(event, data, to=sid)


manager = ConnectionManager()


@sio.event
async def connect(sid, environ):
    logger.info(f"Client {sid} connected")


@sio.event
async def disconnect(sid):
    logger.info(f"Client {sid} disconnected")


@sio.on("join_call")
async def join_call(sid, data):
    """User joins a call room."""
    call_id = data.get("call_id")
    user_id = data.get("user_id")
    await manager.connect(call_id, user_id, sid)
    await sio.emit("user_joined", {"user_id": user_id}, to=call_id)


@sio.on("leave_call")
async def leave_call(sid, data):
    """User leaves a call room."""
    call_id = data.get("call_id")
    user_id = data.get("user_id")
    await manager.disconnect(call_id, user_id, sid)
    await sio.emit("user_left", {"user_id": user_id}, to=call_id)


def app(fast_app: FastAPI, sio_server: socketio.AsyncServer) -> FastAPI:
    """Attach Socket.IO to FastAPI app."""
    asgi_app = socketio.ASGIApp(sio_server, fast_app)
    return asgi_app
