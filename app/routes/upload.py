import os
import shutil
import asyncio
import json

from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from app.worker.tasks import process_file_task
from app.worker.celery_app import celery_app

router = APIRouter(tags=["File Upload"])

@router.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    original_path: str = Form(...)
):
    """
    Accept a document and send it to the Redis queue for background indexing.
    """
    try:
        os.makedirs("temp", exist_ok=True)
        temp_path = os.path.join("temp", file.filename)

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # send the Celery task to Redis!
        task = process_file_task.delay(temp_path, original_path)

        return {
            "status": "success",
            "message": "File queued for indexing",
            "filename": file.filename,
            "task_id": task.id  # The frontend needs this ID for the stream
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Server-Sent Events (SSE) endpoint to stream real-time task progress to the frontend.
    """
    async def event_generator():
        while True:
            # 1.  current status of the task
            task = celery_app.AsyncResult(task_id)
            
            # 2. Constructing the payload
            payload = {
                "task_id": task_id,
                "status": task.status,
                # Include the file path if successs
                "result": task.result if task.status == "SUCCESS" else None
            }
            
            # 3. Yield the data in standard SSE format (data: {...}\n\n)
            yield f"data: {json.dumps(payload)}\n\n"
            
            # 4. If finished or failed, break the loop to close the HTTP connection
            if task.status in ["SUCCESS", "FAILURE", "REVOKED"]:
                break
                
            # 5. Wait fir 1 second before asking Redis again
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")