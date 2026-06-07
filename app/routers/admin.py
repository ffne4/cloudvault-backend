from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User, File, Folder, SharedLink, Bookmark
from app.routers.auth import get_user_from_token
import cloudinary
import cloudinary.uploader

router = APIRouter()

def get_admin_user(authorization: str, db: Session):
    user = get_user_from_token(authorization, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/stats")
def get_system_stats(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    get_admin_user(authorization, db)

    total_users = db.query(User).count()
    total_files = db.query(File).count()
    total_folders = db.query(Folder).count()
    total_public_files = db.query(File).filter(File.is_public == True).count()
    total_shared_links = db.query(SharedLink).count()
    total_bookmarks = db.query(Bookmark).count()

    all_users = db.query(User).all()
    total_storage_used = sum(u.storage_used or 0 for u in all_users)

    return {
        "total_users": total_users,
        "total_files": total_files,
        "total_folders": total_folders,
        "total_public_files": total_public_files,
        "total_shared_links": total_shared_links,
        "total_bookmarks": total_bookmarks,
        "total_storage_used": total_storage_used
    }

@router.get("/users")
def get_all_users(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    get_admin_user(authorization, db)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "storage_used": u.storage_used,
            "created_at": u.created_at,
            "file_count": db.query(File).filter(File.user_id == u.id).count()
        }
        for u in users
    ]

@router.get("/files")
def get_all_files(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    get_admin_user(authorization, db)
    files = db.query(File).order_by(File.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "file_size": f.file_size,
            "file_type": f.file_type,
            "is_public": f.is_public,
            "cloudinary_url": f.cloudinary_url,
            "created_at": f.created_at,
            "owner": {
                "id": f.owner.id,
                "name": f.owner.name,
                "email": f.owner.email
            }
        }
        for f in files
    ]

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_user(authorization, db)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    files = db.query(File).filter(File.user_id == user_id).all()
    for file in files:
        for resource_type in ["image", "video", "raw", "auto"]:
            try:
                result = cloudinary.uploader.destroy(
                    file.cloudinary_public_id,
                    resource_type=resource_type
                )
                if result.get("result") == "ok":
                    break
            except:
                continue

    db.delete(user)
    db.commit()
    return {"message": f"User {user.name} deleted successfully"}

@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    get_admin_user(authorization, db)
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    for resource_type in ["image", "video", "raw", "auto"]:
        try:
            result = cloudinary.uploader.destroy(
                file.cloudinary_public_id,
                resource_type=resource_type
            )
            if result.get("result") == "ok":
                break
        except:
            continue

    owner = db.query(User).filter(User.id == file.user_id).first()
    if owner:
        owner.storage_used = max(0, (owner.storage_used or 0) - file.file_size)

    db.delete(file)
    db.commit()
    return {"message": "File deleted successfully"}

@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_user(authorization, db)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = "admin" if user.role == "user" else "user"
    db.commit()
    return {
        "message": f"{user.name} is now {'an admin' if user.role == 'admin' else 'a regular user'}",
        "role": user.role
    }