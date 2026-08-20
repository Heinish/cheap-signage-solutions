import datetime
import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from .. import security
from ..db import SessionLocal, get_db
from ..models import Device
from ..ws_manager import manager

router = APIRouter()


@router.websocket("/ws/agent")
async def agent_socket(websocket: WebSocket, token: str = Query(...)):
    db: Session = SessionLocal()
    try:
        device = db.query(Device).filter(Device.auth_token == token).first()
        if not device:
            await websocket.close(code=4001)
            return

        await websocket.accept()
        manager.connect_agent(device.id, websocket)
        device.last_seen = datetime.datetime.utcnow()
        db.commit()
        await manager.broadcast_ui({"type": "device_online", "device_id": device.id})

        try:
            while True:
                message = await websocket.receive_json()
                msg_type = message.get("type")

                if msg_type == "heartbeat":
                    device.last_seen = datetime.datetime.utcnow()
                    status_payload = message.get("status") or {}
                    device.last_status_json = json.dumps(status_payload)
                    if status_payload.get("current_url"):
                        device.current_url = status_payload["current_url"]
                    db.commit()
                    await manager.broadcast_ui({
                        "type": "device_status",
                        "device_id": device.id,
                        "status": status_payload,
                    })

                elif msg_type == "result":
                    request_id = message.get("request_id")
                    if request_id:
                        manager.resolve_command(request_id, message)

        except WebSocketDisconnect:
            pass
    finally:
        manager.disconnect_agent(device.id) if 'device' in locals() and device else None
        if 'device' in locals() and device:
            await manager.broadcast_ui({"type": "device_offline", "device_id": device.id})
        db.close()


@router.websocket("/ws/ui")
async def ui_socket(websocket: WebSocket):
    token = websocket.cookies.get("css_session")
    admin_id = security.verify_session(token) if token else None
    if not admin_id:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    manager.connect_ui(websocket)
    try:
        while True:
            # UI doesn't send anything meaningful; just keep the socket alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_ui(websocket)
