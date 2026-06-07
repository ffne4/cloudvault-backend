from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, files, folders, share, public, admin
from app.database import engine
from app.models import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CloudVault API",
    description="A cloud file management system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://cloudvault12.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(folders.router, prefix="/api/folders", tags=["Folders"])
app.include_router(share.router, prefix="/api/share", tags=["Share"])
app.include_router(public.router, prefix="/api/public", tags=["Public"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

@app.get("/")
def root():
    return {"message": "Welcome to CloudVault API 🚀"}