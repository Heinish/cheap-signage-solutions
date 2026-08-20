from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_admin
from ..models import Room, Device
from ..schemas import RoomCreate, RoomOut

router = APIRouter(prefix="/api/rooms", tags=["rooms"], dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(Room).order_by(Room.name).all()


@router.post("", response_model=RoomOut)
def create_room(body: RoomCreate, db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Room name is required")
    if db.query(Room).filter(Room.name == name).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A room with that name already exists")

    room = Room(name=name)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.delete("/{room_id}")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")

    db.query(Device).filter(Device.room_id == room_id).update({"room_id": None})
    db.delete(room)
    db.commit()
    return {"success": True}
