import os
import logging
from app.database import SessionLocal
from app.models import File, FileContent  
from app.processing import process
from sqlalchemy import text

logger = logging.getLogger(__name__)

def generate_file_relationships(source_file_id: str, db, threshold: float = 0.50):
    """
    Cross-references a newly indexed file's vectors against the entire database 
    using pgvector's native cosine distance operator (<=>).
    """
    try:
        logger.info(f"Calculating vector relationships for file: {source_file_id}")
        
        sql_query = text("""
            INSERT INTO file_relationships (source_file_id, target_file_id, similarity_score)
            SELECT 
                :source_id AS source_file_id,
                target_contents.file_id AS target_file_id,
                MAX(1 - (source_contents.embedding <=> target_contents.embedding)) AS similarity_score
            FROM 
                file_content AS source_contents
            CROSS JOIN 
                file_content AS target_contents
            WHERE 
                source_contents.file_id = :source_id
                AND target_contents.file_id != :source_id
            GROUP BY 
                target_contents.file_id
            HAVING 
                MAX(1 - (source_contents.embedding <=> target_contents.embedding)) >= :threshold
            ON CONFLICT (source_file_id, target_file_id) 
            DO UPDATE SET similarity_score = EXCLUDED.similarity_score;
        """)

        db.execute(sql_query, {
            "source_id": str(source_file_id),
            "threshold": threshold
        })
        db.commit()
        logger.info("Successfully mapped relationships.")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to generate relationships: {str(e)}")

def background_index_file(temp_file_path: str):
    """
    Background task that processes a document, extracts AI embeddings,
    saves them to pgvector, and cleans up the temporary file.
    """
    db = SessionLocal()
    file_obj = None  # <-- 1. SAFE INITIALIZATION
    
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

        # Permanently saving the vectors
        db.commit()
        logger.info(f"Successfully indexed {len(file_rows)} file(s) and {len(content_rows)} chunks.")
        
        # <-- 2. SAFE CHECK: Only map relationships if we successfully extracted content
        if file_obj is not None:
            generate_file_relationships(source_file_id=file_obj.id, db=db)
        else:
            logger.warning("No content extracted; skipping relationship generation.")

    except Exception as e:
        # Undoing the changes if anything fails
        db.rollback()
        logger.error(f"Failed to index file {temp_file_path}: {str(e)}")
        
    finally:
        db.close()
        # Deleting the temporary files 
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Cleaned up temporary file: {temp_file_path}")