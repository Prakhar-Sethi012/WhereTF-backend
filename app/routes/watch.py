from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import SessionLocal
from app.models import WatchedFolder

router = APIRouter(tags=["Watch"])


class WatchFolderRequest(BaseModel):
    folder_path: str


@router.post("/watch/folder")
def add_watch_folder(req: WatchFolderRequest):

    db = SessionLocal()

    try:
        existing = db.query(WatchedFolder).filter_by(
            folder_path=req.folder_path
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Folder is already being watched."
            )

        watched_folder = WatchedFolder(
            folder_path=req.folder_path
        )

        db.add(watched_folder)
        db.commit()
        db.refresh(watched_folder)

        return {
            "success": True,
            "id": watched_folder.id,
            "folder_path": watched_folder.folder_path
        }

    finally:
        db.close()


@router.get("/watch/folders")
def get_watched_folders():

    db = SessionLocal()

    try:
        folders = db.query(WatchedFolder).all()

        return [
            {
                "id": folder.id,
                "folder_path": folder.folder_path,
                "created_at": folder.created_at
            }
            for folder in folders
        ]

    finally:
        db.close()


@router.delete("/watch/folder")
def remove_watch_folder(req: WatchFolderRequest):

    db = SessionLocal()

    try:
        folder = db.query(WatchedFolder).filter_by(
            folder_path=req.folder_path
        ).first()

        if not folder:
            raise HTTPException(
                status_code=404,
                detail="Folder not found."
            )

        db.delete(folder)
        db.commit()

        return {
            "success": True
        }

    finally:
        db.close()