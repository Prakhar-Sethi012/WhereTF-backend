import os
import logging
from app.database import SessionLocal
from app.models import File, FileContent  
from app.processing import process

logger = logging.getLogger(__name__)

def background_index_file(temp_file_path: str):
    """
    Background task that processes a document, extracts AI embeddings,
    saves them to pgvector, and cleans up the temporary file.
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Starting background indexing for: {temp_file_path}")
        
        file_rows, content_rows = process(temp_file_path)
        for fr in file_rows:
            existing = db.query(File).filter_by(file_path=fr["file_path"]).first()
            if existing:
                for k, v in fr.items():
                    setattr(existing, k, v)
            else:
                db.add(File(**fr))
                
        db.flush()  

        for cr in content_rows:
            file_path = cr.pop("file_path")
            file_obj = db.query(File).filter_by(file_path=file_path).one()
            
            db.add(FileContent(
                file_id=file_obj.id,
                chunk_index=cr["chunk_index"],
                content_text=cr["content_text"],
                embedding=cr["embedding"]
            ))

        # permanently saving the vectors
        db.commit()
        logger.info(f"Successfully indexed {len(file_rows)} file(s) and {len(content_rows)} chunks.")

    except Exception as e:
        # undo the changes if anything fails
        db.rollback()
        logger.error(f"Failed to index file {temp_file_path}: {str(e)}")
        
    finally:
        db.close()
        
        # Server Cleanup,deleting the temp files 
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Cleaned up temporary file: {temp_file_path}")