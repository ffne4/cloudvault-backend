from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import os

load_dotenv()

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

# Schemas
class RegisterSchema(BaseModel):
    name: str
    email: str
    password: str

class LoginSchema(BaseModel):
    email: str
    password: str

class UpdateProfileSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

class UpdatePasswordSchema(BaseModel):
    current_password: str
    new_password: str

# Helpers
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user = db.query(User).filter(User.email == email).first()
        return user
    except JWTError:
        return None

def get_user_from_token(authorization: str, db: Session):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    user = get_current_user(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# Routes
@router.post("/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Account created successfully"}

@router.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "storage_used": user.storage_used
        }
    }

@router.get("/me")
def get_me(authorization: str = Header(None), db: Session = Depends(get_db)):
    user = get_user_from_token(authorization, db)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "storage_used": user.storage_used,
        "created_at": user.created_at
    }

@router.patch("/profile")
def update_profile(
    data: UpdateProfileSchema,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)

    if data.email and data.email != user.email:
        existing = db.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email

    if data.name:
        user.name = data.name

    db.commit()
    db.refresh(user)

    # Issue new token if email changed
    new_token = create_access_token({"sub": user.email})
    return {
        "message": "Profile updated successfully",
        "token": new_token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "storage_used": user.storage_used
        }
    }

@router.patch("/password")
def update_password(
    data: UpdatePasswordSchema,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(authorization, db)

    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}

@router.get("/stats")
def get_my_stats(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from app.models.models import File, Folder, SharedLink, Bookmark
    user = get_user_from_token(authorization, db)

    total_files = db.query(File).filter(File.user_id == user.id).count()
    total_folders = db.query(Folder).filter(Folder.user_id == user.id).count()
    public_files = db.query(File).filter(
        File.user_id == user.id,
        File.is_public == True
    ).count()
    total_shares = db.query(SharedLink).join(File).filter(
        File.user_id == user.id
    ).count()
    total_bookmarks = db.query(Bookmark).filter(
        Bookmark.user_id == user.id
    ).count()

    return {
        "total_files": total_files,
        "total_folders": total_folders,
        "public_files": public_files,
        "total_shares": total_shares,
        "total_bookmarks": total_bookmarks
    }
@router.delete("/account")
def delete_account(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from app.models.models import File
    import cloudinary
    import cloudinary.uploader

    user = get_user_from_token(authorization, db)

    # Delete all files from Cloudinary
    files = db.query(File).filter(File.user_id == user.id).all()
    for file in files:
        try:
            cloudinary.uploader.destroy(file.cloudinary_public_id, resource_type="auto")
        except:
            pass

    db.delete(user)
    db.commit()
    return {"message": "Account deleted successfully"}