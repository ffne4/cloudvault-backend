from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Folder
from app.routers.auth import get_current_user
from pydantic import BaseModel

router = APIRouter()

def get_user_from_token(authorization: str, db: Session):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    user = get_current_user(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

class FolderSchema(BaseModel):
    name: str
    parent_folder_id: int = None

@router.post("/")
def create_folder(
    data: FolderSchema,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    folder = Folder(
        user_id=user.id,
        name=data.name,
        parent_folder_id=data.parent_folder_id
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"message": "Folder created", "folder": {"id": folder.id, "name": folder.name}}

@router.get("/")
def get_folders(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    folders = db.query(Folder).filter(Folder.user_id == user.id).all()
    return [{"id": f.id, "name": f.name, "parent_folder_id": f.parent_folder_id} for f in folders]

@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)
    folder = db.query(Folder).filter(Folder.id == folder_id, Folder.user_id == user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    db.delete(folder)
    db.commit()
    return {"message": "Folder deleted"}