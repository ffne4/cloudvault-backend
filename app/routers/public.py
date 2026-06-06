from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import File, User, Bookmark
from app.routers.auth import get_current_user
from typing import Optional

router = APIRouter()

def get_user_from_token(authorization: str, db: Session):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    user = get_current_user(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

def format_file(f, current_user_id=None, db=None):
    bookmarked = False
    if current_user_id and db:
        bookmarked = db.query(Bookmark).filter(
            Bookmark.user_id == current_user_id,
            Bookmark.file_id == f.id
        ).first() is not None
    return {
        "id": f.id,
        "filename": f.filename,
        "url": f.cloudinary_url,
        "size": f.file_size,
        "type": f.file_type,
        "is_public": f.is_public,
        "created_at": f.created_at,
        "owner": {
            "id": f.owner.id,
            "name": f.owner.name,
        },
        "bookmarked": bookmarked,
        "bookmark_count": len(f.bookmarks)
    }

# Toggle file public/private
@router.patch("/toggle/{file_id}")
def toggle_public(
    file_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    file = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    file.is_public = not file.is_public
    db.commit()
    return {
        "message": f"File is now {'public' if file.is_public else 'private'}",
        "is_public": file.is_public
    }

# Get all public files (discovery feed)
@router.get("/feed")
def get_public_feed(
    search: Optional[str] = Query(None),
    file_type: Optional[str] = Query(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    query = db.query(File).filter(File.is_public == True)

    if search:
        query = query.filter(File.filename.ilike(f"%{search}%"))
    if file_type == "image":
        query = query.filter(File.file_type.ilike("image/%"))
    elif file_type == "video":
        query = query.filter(File.file_type.ilike("video/%"))
    elif file_type == "document":
        query = query.filter(File.file_type.ilike("%pdf%"))

    files = query.order_by(File.created_at.desc()).all()
    return [format_file(f, user.id, db) for f in files]

# Get public files by a specific user
@router.get("/user/{user_id}")
def get_user_public_files(
    user_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    files = db.query(File).filter(
        File.user_id == user_id,
        File.is_public == True
    ).order_by(File.created_at.desc()).all()

    return {
        "user": {"id": target.id, "name": target.name},
        "files": [format_file(f, user.id, db) for f in files]
    }

# Bookmark a file
@router.post("/bookmark/{file_id}")
def bookmark_file(
    file_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    file = db.query(File).filter(File.id == file_id, File.is_public == True).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found or not public")

    existing = db.query(Bookmark).filter(
        Bookmark.user_id == user.id,
        Bookmark.file_id == file_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"message": "Bookmark removed", "bookmarked": False}

    bookmark = Bookmark(user_id=user.id, file_id=file_id)
    db.add(bookmark)
    db.commit()
    return {"message": "File bookmarked", "bookmarked": True}

# Get my bookmarks
@router.get("/bookmarks")
def get_my_bookmarks(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    bookmarks = db.query(Bookmark).filter(Bookmark.user_id == user.id).all()
    return [format_file(b.file, user.id, db) for b in bookmarks]