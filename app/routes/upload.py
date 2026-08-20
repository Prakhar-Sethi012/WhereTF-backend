import os
import shutil
import asyncio
import json
import uuid  # <-- Added for secure filenames

from fastapi import APIRouter, Form, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.worker.tasks import process_file_task
from app.worker.celery_app import celery_app

router = APIRouter(tags=["File Upload"])

@router.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    original_path: str = Form(...)
):
    try:
        os.makedirs("temp", exist_ok=True)
        fallback_name=file.filename or "unnamed_upload"
        # FIX 5: Secure the filename to prevent path traversal & collisions
        safe_filename = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
        temp_path = os.path.join("temp", safe_filename)

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        task = process_file_task.delay(temp_path, original_path)

        return {
            "status": "success",
            "message": "File queued for indexing",
            "filename": safe_filename,
            "task_id": task.id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )

@router.get("/status/{task_id}")
async def get_task_status(task_id: str, request: Request): # <-- FIX 7: Added Request parameter
    async def event_generator():
        while True:
            # FIX 7: Safely kill the loop if the user closes their browser tab
            if await request.is_disconnected():
                break
                
            task = celery_app.AsyncResult(task_id)
            payload = {
                "task_id": task_id,
                "status": task.status,
                "result": task.result if task.status == "SUCCESS" else None
            }
            
            yield f"data: {json.dumps(payload)}\n\n"
            
            if task.status in ["SUCCESS", "FAILURE", "REVOKED"]:
                break
                
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")