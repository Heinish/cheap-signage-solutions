from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import config, security
from .db import get_db
from .models import AdminUser


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    admin_id = security.verify_session(token) if token else None
    if not admin_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    admin = db.get(AdminUser, admin_id)
    if not admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return admin
