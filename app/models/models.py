from sqlalchemy import Column, Integer, String, BigInteger, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    storage_used = Column(BigInteger, default=0)
    role = Column(String(20), default="user")
    created_at = Column(TIMESTAMP, server_default=func.now())

    files = relationship("File", back_populates="owner", cascade="all, delete")
    folders = relationship("Folder", back_populates="owner", cascade="all, delete")
    bookmarks = relationship("Bookmark", back_populates="user", cascade="all, delete")


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    parent_folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    owner = relationship("User", back_populates="folders")
    files = relationship("File", back_populates="folder")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(String(50))
    cloudinary_url = Column(String, nullable=False)
    cloudinary_public_id = Column(String, nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    owner = relationship("User", back_populates="files")
    folder = relationship("Folder", back_populates="files")
    shared_links = relationship("SharedLink", back_populates="file", cascade="all, delete")
    bookmarks = relationship("Bookmark", back_populates="file", cascade="all, delete")


class SharedLink(Base):
    __tablename__ = "shared_links"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=True)
    is_public = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    file = relationship("File", back_populates="shared_links")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="bookmarks")
    file = relationship("File", back_populates="bookmarks")