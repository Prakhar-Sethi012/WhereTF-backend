# code for file-idexing,addition and updation of tags and deleting a specific file

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from app.models.relationship import FileRelationship
from app.database import get_db
from app.models import File

router = APIRouter(prefix="/files", tags=["files"])

# --- Pydantic Schema for the PATCH request ---
class FileUpdatePayload(BaseModel):
    tags: Optional[List[str]] = None
    context: Optional[str] = None

# 1. THE DASHBOARD: Get all files
@router.get("/")
def get_all_files(db: Session = Depends(get_db)):
    """Returns a list of all indexed files for the frontend UI."""
    files = db.execute(select(File)).scalars().all()
    
    return [
        {
            "id": str(f.id),
            "file_path": f.file_path,
            "mime_type": f.mime_type,
            "tags": f.tags,
            "context": f.context,
            "last_modified": f.last_modified
        }
        for f in files
    ]

# 2. THE METADATA MANAGER: Update tags and context
@router.patch("/{file_id}")
def update_file_metadata(file_id: uuid.UUID, payload: FileUpdatePayload, db: Session = Depends(get_db)):
    """Updates the user-defined tags and context for a specific file."""
    db_file = db.scalar(select(File).where(File.id == file_id))
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if payload.tags is not None:
        db_file.tags = payload.tags
    if payload.context is not None:
        db_file.context = payload.context
        
    db.commit()
    db.refresh(db_file)
    
    return {"status": "success", "message": "Metadata updated", "file_id": str(db_file.id)}

# 3. THE ERASER: Delete a file and its vectors
@router.delete("/{file_id}")
def delete_file(file_id: uuid.UUID, db: Session = Depends(get_db)):
    """Deletes a file and all its associated AI chunks automatically."""
    db_file = db.scalar(select(File).where(File.id == file_id))
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
        
    db.delete(db_file)
    db.commit()
    
    return {"status": "success", "message": f"File and vectors wiped successfully."}

# 4. File relationship
@router.get("/{file_id}/related")
def get_related_files(file_id: uuid.UUID, db: Session = Depends(get_db)):
    """Returns a list of files mathematically related to the requested file."""
    
    # Check if the file exists
    db_file = db.scalar(select(File).where(File.id == file_id))
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Fetch relationships where this file is the source
    relationships = db.execute(
        select(FileRelationship, File)
        .join(File, FileRelationship.target_file_id == File.id)
        .where(FileRelationship.source_file_id == file_id)
        .order_by(FileRelationship.similarity_score.desc())
    ).all()

    return {
        "status": "success",
        "file_id": str(file_id),
        "related_files": [
            {
                "target_file_id": str(rel.FileRelationship.target_file_id),
                "similarity_score": round(rel.FileRelationship.similarity_score, 4),
                "file_path": rel.File.file_path,
                "mime_type": rel.File.mime_type
            }
            for rel in relationships
        ]
    }