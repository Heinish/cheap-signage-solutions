import asyncio
import uuid
from typing import Any

from fastapi import WebSocket

from . import config


class DeviceOffline(Exception):
    pass


class CommandTimeout(Exception):
    pass


class ConnectionManager:
    """Tracks live WebSocket connections: one per paired Pi agent, plus
    any browser/UI clients listening for live fleet updates."""

    def __init__(self):
        self.agents: dict[int, WebSocket] = {}
        self.pending: dict[str, asyncio.Future] = {}
        self.ui_clients: set[WebSocket] = set()

    # ---- Agents ----

    def connect_agent(self, device_id: int, ws: WebSocket):
        self.agents[device_id] = ws

    def disconnect_agent(self, device_id: int):
        self.agents.pop(device_id, None)
        # Fail any commands still waiting on this device
        stale = [rid for rid, fut in self.pending.items() if getattr(fut, "_device_id", None) == device_id]
        for rid in stale:
            fut = self.pending.pop(rid, None)
            if fut and not fut.done():
                fut.set_exception(DeviceOffline())

    def is_online(self, device_id: int) -> bool:
        return device_id in self.agents

    async def send_command(self, device_id: int, action: str, params: dict) -> dict[str, Any]:
        ws = self.agents.get(device_id)
        if ws is None:
            raise DeviceOffline()

        request_id = uuid.uuid4().hex
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        fut._device_id = device_id  # type: ignore[attr-defined]
        self.pending[request_id] = fut

        try:
            await ws.send_json({"type": "command", "request_id": request_id, "action": action, "params": params})
        except Exception:
            self.pending.pop(request_id, None)
            raise DeviceOffline()

        try:
            return await asyncio.wait_for(fut, timeout=config.COMMAND_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            raise CommandTimeout()
        finally:
            self.pending.pop(request_id, None)

    def resolve_command(self, request_id: str, payload: dict):
        fut = self.pending.get(request_id)
        if fut and not fut.done():
            fut.set_result(payload)

    # ---- UI clients ----

    def connect_ui(self, ws: WebSocket):
        self.ui_clients.add(ws)

    def disconnect_ui(self, ws: WebSocket):
        self.ui_clients.discard(ws)

    async def broadcast_ui(self, message: dict):
        dead = []
        for ws in self.ui_clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.ui_clients.discard(ws)


manager = ConnectionManager()
