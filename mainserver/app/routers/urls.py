from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_admin
from ..models import SavedUrl
from ..schemas import SavedUrlCreate, SavedUrlOut

router = APIRouter(prefix="/api/urls", tags=["urls"], dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[SavedUrlOut])
def list_urls(db: Session = Depends(get_db)):
    return db.query(SavedUrl).order_by(SavedUrl.name).all()


@router.post("", response_model=SavedUrlOut)
def create_url(body: SavedUrlCreate, db: Session = Depends(get_db)):
    if not body.url.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "URL is required")

    saved = SavedUrl(name=body.name.strip() or body.url.strip(), url=body.url.strip())
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved


@router.delete("/{url_id}")
def delete_url(url_id: int, db: Session = Depends(get_db)):
    saved = db.get(SavedUrl, url_id)
    if not saved:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "URL not found")
    db.delete(saved)
    db.commit()
    return {"success": True}
