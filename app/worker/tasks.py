import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from celery.utils.log import get_task_logger
from datetime import datetime, timezone

from app.database import SessionLocal # NOTE: Change this to app.db if you apply Fix 1!
from app.models import File
from app.worker.celery_app import celery_app
from app.services.indexer import background_index_file

logger = get_task_logger(__name__)

@celery_app.task(bind=True, name="process_file_task")
def process_file_task(self, temp_path: str, original_path: str):
    logger.info(f"Starting Celery indexing job for file: {original_path}")
    
    db: Session = SessionLocal()
    
    try:
        # 1. Try to find the file
        file_record = db.query(File).filter(File.file_path == original_path).first()
        
        if not file_record:
            file_record = File(
                file_path=original_path,
                file_hash="pending", 
                mime_type="unknown",
                last_modified=datetime.now(timezone.utc),
                state="processing"
            )
            db.add(file_record)
            try:
                # 2. Try to save it
                db.commit()
            except IntegrityError:
                # FIX 9: Race Condition Caught! Another worker just created this row.
                db.rollback()
                file_record = db.query(File).filter(File.file_path == original_path).first()
                file_record.state = "processing"
                db.commit()
        else:
            file_record.state = "processing"
            db.commit()
            
        db.refresh(file_record)

        # 3. Process AI Embeddings
        logger.info(f"Handing off to AI indexer for {original_path}...")
        background_index_file(temp_path, original_path)

        # 4. Mark as Done
        file_record = db.query(File).filter(File.file_path == original_path).first()
        if file_record:
            file_record.state = "indexed"
            db.commit()
        
        logger.info(f"Successfully finished Celery job for: {original_path}")
        return {"status": "success", "file_path": original_path}

    except Exception as e:
        logger.error(f"Task failed for {original_path}: {str(e)}")
        db.rollback()
        
        file_record = db.query(File).filter(File.file_path == original_path).first()
        if file_record:
            file_record.state = "failed"
            db.commit()
            
        raise e
        
    finally:
        db.close()
        
        # Guaranteed Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"Cleaned up temp file: {temp_path}")