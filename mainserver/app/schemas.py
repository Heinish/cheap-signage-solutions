import datetime
from typing import Optional, Any

from pydantic import BaseModel


class SetupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RoomCreate(BaseModel):
    name: str


class RoomOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class SavedUrlCreate(BaseModel):
    name: str
    url: str


class SavedUrlOut(BaseModel):
    id: int
    name: str
    url: str

    class Config:
        from_attributes = True


class DeviceOut(BaseModel):
    id: int
    device_uid: str
    name: str
    room_id: Optional[int]
    room_name: Optional[str] = None
    online: bool
    last_seen: Optional[datetime.datetime]
    current_url: Optional[str]
    status: Optional[dict] = None

    class Config:
        from_attributes = True


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    room_id: Optional[int] = None


class PairRequest(BaseModel):
    device_uid: str


class PairClaim(BaseModel):
    code: str
    name: str
    room_id: Optional[int] = None


class CommandRequest(BaseModel):
    action: str
    params: dict[str, Any] = {}
