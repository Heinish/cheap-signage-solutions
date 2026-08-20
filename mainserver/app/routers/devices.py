import base64
import datetime
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..deps import get_current_admin
from ..models import Device, Room
from ..schemas import CommandRequest, DeviceOut, DeviceUpdate
from ..ws_manager import CommandTimeout, DeviceOffline, manager

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(get_current_admin)])


def _is_online(device: Device) -> bool:
    return manager.is_online(device.id)


def _to_out(device: Device) -> DeviceOut:
    status_dict = json.loads(device.last_status_json) if device.last_status_json else None
    return DeviceOut(
        id=device.id,
        device_uid=device.device_uid,
        name=device.name,
        room_id=device.room_id,
        room_name=device.room.name if device.room else None,
        online=_is_online(device),
        last_seen=device.last_seen,
        current_url=device.current_url,
        status=status_dict,
    )


@router.get("", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(Device.name).all()
    return [_to_out(d) for d in devices]


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return _to_out(device)


@router.patch("/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, body: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Name cannot be empty")
        device.name = name
    if body.room_id is not None:
        if body.room_id != 0 and not db.get(Room, body.room_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Room not found")
        device.room_id = body.room_id or None

    db.commit()
    db.refresh(device)
    return _to_out(device)


@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    db.delete(device)
    db.commit()
    return {"success": True}


async def _run_command(db: Session, device: Device, action: str, params: dict) -> dict:
    try:
        result = await manager.send_command(device.id, action, params)
    except DeviceOffline:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{device.name} is offline")
    except CommandTimeout:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, f"{device.name} did not respond in time")

    if action == "set_url" and result.get("success") and "url" in params:
        device.current_url = params["url"]
        db.commit()

    return result


def _get_device_or_404(db: Session, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return device


@router.post("/{device_id}/command")
async def send_command(device_id: int, body: CommandRequest, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, body.action, body.params)


@router.post("/{device_id}/url")
async def set_url(device_id: int, body: dict, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    url = (body or {}).get("url")
    if not url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "url is required")
    return await _run_command(db, device, "set_url", {"url": url})


@router.post("/{device_id}/reboot")
async def reboot(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "reboot", {})


@router.post("/{device_id}/browser/restart")
async def restart_browser(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "restart_browser", {})


@router.post("/{device_id}/rotate")
async def rotate(device_id: int, body: dict, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    rotation = (body or {}).get("rotation")
    if rotation not in (0, 90, 180, 270):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "rotation must be 0, 90, 180, or 270")
    return await _run_command(db, device, "rotate", {"rotation": rotation})


@router.get("/{device_id}/screenshot")
async def screenshot(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    result = await _run_command(db, device, "screenshot", {})
    if not result.get("success"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, result.get("error", "Screenshot failed"))
    return {"image_base64": result.get("image_base64")}


@router.post("/{device_id}/update")
async def update_agent(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "update", {})


@router.post("/{device_id}/network")
async def network_config(device_id: int, body: dict, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "network_config", body or {})


@router.get("/{device_id}/settings")
async def get_settings(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "get_settings", {})


@router.post("/{device_id}/settings")
async def set_settings(device_id: int, body: dict, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "set_settings", body or {})


# ---- Image / playlist ----

@router.post("/{device_id}/image")
async def upload_image(device_id: int, db: Session = Depends(get_db), image: UploadFile = File(...)):
    device = _get_device_or_404(db, device_id)
    data = await image.read()
    return await _run_command(
        db, device, "image_upload",
        {"filename": image.filename, "data_base64": base64.b64encode(data).decode()},
    )


@router.delete("/{device_id}/image")
async def delete_image(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "image_delete", {})


@router.get("/{device_id}/playlist")
async def get_playlist(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "playlist_get", {})


@router.post("/{device_id}/playlist")
async def set_playlist(device_id: int, body: dict, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "playlist_set", body or {})


@router.delete("/{device_id}/playlist")
async def clear_playlist(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "playlist_clear", {})


@router.post("/{device_id}/playlist/images")
async def upload_playlist_image(device_id: int, db: Session = Depends(get_db), image: UploadFile = File(...)):
    device = _get_device_or_404(db, device_id)
    data = await image.read()
    return await _run_command(
        db, device, "playlist_image_upload",
        {"filename": image.filename, "data_base64": base64.b64encode(data).decode()},
    )


@router.delete("/{device_id}/playlist/images/{index}")
async def delete_playlist_image(device_id: int, index: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "playlist_image_delete", {"index": index})


@router.post("/{device_id}/playlist/activate")
async def activate_playlist(device_id: int, db: Session = Depends(get_db)):
    device = _get_device_or_404(db, device_id)
    return await _run_command(db, device, "playlist_activate", {})
