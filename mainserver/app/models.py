import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from .db import Base


def utcnow():
    return datetime.datetime.utcnow()


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    devices = relationship("Device", back_populates="room")


class SavedUrl(Base):
    __tablename__ = "saved_urls"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    url = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_uid = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    auth_token = Column(String(64), unique=True, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)

    last_seen = Column(DateTime, nullable=True)
    last_status_json = Column(Text, nullable=True)  # cached heartbeat payload
    current_url = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    room = relationship("Room", back_populates="devices")


class PendingPairing(Base):
    __tablename__ = "pending_pairings"

    id = Column(Integer, primary_key=True)
    device_uid = Column(String(64), unique=True, nullable=False)
    code = Column(String(16), unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    claimed_device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
