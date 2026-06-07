from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Header, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import File, User
from app.routers.auth import get_current_user
from pydantic import BaseModel
from typing import Optional
import cloudinary
import cloudinary.uploader
import cloudinary.utils
from dotenv import load_dotenv
import os

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

router = APIRouter()

def get_user_from_token(authorization: str, db: Session):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    user = get_current_user(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

def get_resource_type(content_type: str) -> str:
    if not content_type:
        return "raw"
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/") or content_type.startswith("audio/"):
        return "video"
    return "raw"

def get_view_url(cloudinary_url: str, content_type: str, filename: str) -> str:
    """Generate a proper viewing URL for different file types"""
    if not content_type:
        return cloudinary_url
    # Images and videos display fine as-is
    if content_type.startswith("image/") or content_type.startswith("video/"):
        return cloudinary_url
    # For PDFs and documents use Google Docs viewer
    encoded_url = cloudinary_url.replace(":", "%3A").replace("/", "%2F")
    if content_type.includes("pdf") if hasattr(content_type, 'includes') else "pdf" in content_type:
        return f"https://docs.google.com/viewer?url={cloudinary_url}&embedded=true"
    if any(x in content_type for x in ["word", "document", "msword", "officedocument.word"]):
        return f"https://docs.google.com/viewer?url={cloudinary_url}&embedded=true"
    if any(x in content_type for x in ["powerpoint", "presentation", "officedocument.presentation"]):
        return f"https://docs.google.com/viewer?url={cloudinary_url}&embedded=true"
    if any(x in content_type for x in ["excel", "spreadsheet", "officedocument.sheet"]):
        return f"https://docs.google.com/viewer?url={cloudinary_url}&embedded=true"
    return cloudinary_url

class RenameSchema(BaseModel):
    filename: str

class MoveSchema(BaseModel):
    folder_id: Optional[int] = None

@router.post("/upload")
def upload_file(
    file: UploadFile = FastAPIFile(...),
    folder_id: Optional[int] = None,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)

    content_type = file.content_type or ""
    resource_type = get_resource_type(content_type)

    try:
        result = cloudinary.uploader.upload(
            file.file,
            resource_type=resource_type,
            folder="cloudvault",
            access_mode="public",
            use_filename=True,
            unique_filename=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    new_file = File(
        user_id=user.id,
        folder_id=folder_id,
        filename=file.filename,
        file_size=file.size,
        file_type=file.content_type,
        cloudinary_url=result["secure_url"],
        cloudinary_public_id=result["public_id"]
    )
    db.add(new_file)
    user.storage_used = (user.storage_used or 0) + file.size
    db.commit()
    db.refresh(new_file)

    return {
        "message": "File uploaded successfully",
        "file": {
            "id": new_file.id,
            "filename": new_file.filename,
            "url": new_file.cloudinary_url,
            "size": new_file.file_size,
            "type": new_file.file_type,
            "is_public": new_file.is_public
        }
    }

@router.get("/")
def get_files(
    folder_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    order: Optional[str] = Query("desc"),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    query = db.query(File).filter(File.user_id == user.id)

    if folder_id:
        query = query.filter(File.folder_id == folder_id)
    else:
        query = query.filter(File.folder_id == None)

    if search:
        query = query.filter(File.filename.ilike(f"%{search}%"))

    if sort_by == "filename":
        query = query.order_by(File.filename.asc() if order == "asc" else File.filename.desc())
    elif sort_by == "file_size":
        query = query.order_by(File.file_size.asc() if order == "asc" else File.file_size.desc())
    else:
        query = query.order_by(File.created_at.asc() if order == "asc" else File.created_at.desc())

    files = query.all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "url": f.cloudinary_url,
            "size": f.file_size,
            "type": f.file_type,
            "folder_id": f.folder_id,
            "is_public": f.is_public,
            "created_at": f.created_at
        }
        for f in files
    ]

@router.patch("/{file_id}/rename")
def rename_file(
    file_id: int,
    data: RenameSchema,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    file = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    file.filename = data.filename
    db.commit()
    return {"message": "File renamed successfully"}

@router.patch("/{file_id}/move")
def move_file(
    file_id: int,
    data: MoveSchema,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    file = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    file.folder_id = data.folder_id
    db.commit()
    return {"message": "File moved successfully"}

@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    file = db.query(File).filter(File.id == file_id, File.user_id == user.id).first()
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

    user.storage_used = max(0, (user.storage_used or 0) - file.file_size)
    db.delete(file)
    db.commit()
    return {"message": "File deleted successfully"}