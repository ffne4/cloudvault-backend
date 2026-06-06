from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import SharedLink, File
from app.routers.auth import get_current_user
from datetime import datetime, timedelta
import secrets

router = APIRouter()

def get_user_from_token(authorization: str, db: Session):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    user = get_current_user(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

@router.post("/{file_id}")
def create_share_link(
    file_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    file = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)

    link = SharedLink(
        file_id=file.id,
        token=token,
        expires_at=expires_at,
        is_public=True
    )
    db.add(link)
    db.commit()

    return {
        "share_link": f"http://localhost:8000/api/share/access/{token}",
        "expires_at": expires_at
    }

@router.get("/access/{token}")
def access_shared_file(token: str, db: Session = Depends(get_db)):
    link = db.query(SharedLink).filter(SharedLink.token == token).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    if link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Link has expired")

    file = db.query(File).filter(File.id == link.file_id).first()
    return {
        "filename": file.filename,
        "url": file.cloudinary_url,
        "type": file.file_type
    }