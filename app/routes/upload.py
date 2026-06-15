import os
import shutil

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException

from app.services.indexer import background_index_file

router = APIRouter(tags=["File Upload"])


@router.post("/upload/")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Accept a document and send it for background indexing.
    """

    try:
        os.makedirs("temp", exist_ok=True)

        temp_path = os.path.join("temp", file.filename)

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        background_tasks.add_task(
            background_index_file,
            temp_path
        )

        return {
            "status": "success",
            "message": "File accepted for indexing",
            "filename": file.filename
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )
