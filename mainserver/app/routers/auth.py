from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import config, security
from ..db import get_db
from ..deps import get_current_admin
from ..models import AdminUser
from ..schemas import LoginRequest, SetupRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, admin_id: int):
    token = security.sign_session(admin_id)
    response.set_cookie(
        config.SESSION_COOKIE_NAME,
        token,
        max_age=config.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    needs_setup = db.query(AdminUser).count() == 0
    return {"needs_setup": needs_setup}


@router.post("/setup")
def setup(body: SetupRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(AdminUser).count() > 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Setup already completed")
    if len(body.password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password must be at least 8 characters")

    admin = AdminUser(username=body.username.strip(), password_hash=security.hash_password(body.password))
    db.add(admin)
    db.commit()
    db.refresh(admin)

    _set_session_cookie(response, admin.id)
    return {"success": True, "username": admin.username}


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.username == body.username.strip()).first()
    if not admin or not security.verify_password(body.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    _set_session_cookie(response, admin.id)
    return {"success": True, "username": admin.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(config.SESSION_COOKIE_NAME)
    return {"success": True}


@router.get("/me")
def me(admin: AdminUser = Depends(get_current_admin)):
    return {"username": admin.username}
