import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import config, security
from ..db import get_db
from ..deps import get_current_admin
from ..models import Device, PendingPairing
from ..schemas import PairClaim, PairRequest

router = APIRouter(prefix="/api/pair", tags=["pairing"])


@router.post("/request")
def pair_request(body: PairRequest, db: Session = Depends(get_db)):
    """Called repeatedly by an unpaired Pi agent. Returns a code to show on
    the display until an admin claims it, then returns the device's token."""
    device_uid = body.device_uid.strip()
    if not device_uid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "device_uid is required")

    pending = db.query(PendingPairing).filter(PendingPairing.device_uid == device_uid).first()

    if pending and pending.claimed_device_id:
        device = db.get(Device, pending.claimed_device_id)
        if device:
            db.delete(pending)
            db.commit()
            return {"status": "paired", "token": device.auth_token, "device_id": device.id}

    expired = pending and (
        datetime.datetime.utcnow() - pending.created_at
    ).total_seconds() > config.PAIRING_TTL_SECONDS

    if not pending or expired:
        if pending:
            db.delete(pending)
            db.flush()
        code = security.generate_pairing_code()
        while db.query(PendingPairing).filter(PendingPairing.code == code).first():
            code = security.generate_pairing_code()
        pending = PendingPairing(device_uid=device_uid, code=code)
        db.add(pending)
        db.commit()
        db.refresh(pending)

    return {"status": "pending", "code": pending.code}


@router.get("/pending")
def list_pending(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    rows = (
        db.query(PendingPairing)
        .filter(PendingPairing.claimed_device_id.is_(None))
        .order_by(PendingPairing.created_at.desc())
        .all()
    )
    return [
        {"device_uid": r.device_uid, "code": r.code, "created_at": r.created_at}
        for r in rows
    ]


@router.post("/claim")
def claim(body: PairClaim, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    code = body.code.strip().upper()
    pending = db.query(PendingPairing).filter(PendingPairing.code == code).first()
    if not pending:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pairing request with that code")
    if pending.claimed_device_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code has already been claimed")

    name = body.name.strip() or f"Display {pending.device_uid[:6]}"
    device = Device(
        device_uid=pending.device_uid,
        name=name,
        auth_token=security.generate_device_token(),
        room_id=body.room_id,
    )
    db.add(device)
    db.flush()
    pending.claimed_device_id = device.id
    db.commit()
    db.refresh(device)
    return {"success": True, "device_id": device.id, "name": device.name}
