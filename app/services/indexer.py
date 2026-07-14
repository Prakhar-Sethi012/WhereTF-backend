import os
import shutil
import zipfile
import logging

from sqlalchemy import text

from app.database import SessionLocal
from app.models import File, FileContent
from app.processing import process
from app.services.archive import extract_zip

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


def save_processed_data(db, file_rows, content_rows):
    """
    Save processed file metadata and chunks into the database.
    Returns a list of the saved File objects so relationships can be built.
    """
    saved_files = []

    # 1. Save or update Files
    for fr in file_rows:
        existing = db.query(File).filter_by(file_path=fr["file_path"]).first()

        if existing:
            for k, v in fr.items():
                setattr(existing, k, v)
            saved_files.append(existing)
        else:
            new_file = File(**fr)
            db.add(new_file)
            saved_files.append(new_file)

    # Flush so that new File records receive an auto-generated ID from the database
    db.flush()

    # 2. Save FileContents mapped to the correct File ID
    for cr in content_rows:
        file_path = cr.pop("file_path")
        
        # Match the chunk to the file object we just created/updated
        file_obj = next((f for f in saved_files if f.file_path == file_path), None)
        
        if file_obj:
            db.add(
                FileContent(
                    file_id=file_obj.id,
                    chunk_index=cr["chunk_index"],
                    content_text=cr["content_text"],
                    embedding=cr["embedding"],
                )
            )

    return saved_files


def background_index_file(temp_file_path: str, original_path: str):
    """
    Processes a document (or ZIP archive), generates embeddings,
    stores everything in PostgreSQL, and cleans up temporary files.
    """
    db = SessionLocal()
    all_saved_files = []
    
    try:
        logger.info(f"Starting indexing for: {temp_file_path}")

        # --------------------------------------------------------
        # ZIP ARCHIVE
        # --------------------------------------------------------
        if zipfile.is_zipfile(temp_file_path):
            logger.info("ZIP archive detected.")
            temp_extract_dir, extracted_files = extract_zip(temp_file_path)

            try:
                for extracted in extracted_files:
                    extension = os.path.splitext(extracted)[1].lower()
                    supported = {".pdf", ".docx", ".txt", ".md", ".pptx", ".csv", ".py"}

                    if extension not in supported:
                        logger.info(f"Skipping unsupported file: {extracted}")
                        continue

                    logger.info(f"Processing: {extracted}")
                    archive_path = f"{original_path}::{os.path.relpath(extracted, temp_extract_dir)}"

                    file_rows, content_rows = process(extracted)

                    for fr in file_rows:
                        fr["file_path"] = archive_path
                    for cr in content_rows:
                        cr["file_path"] = archive_path

                    saved = save_processed_data(db, file_rows, content_rows)
                    all_saved_files.extend(saved)

                db.commit()
                logger.info("ZIP archive indexed successfully.")

            finally:
                shutil.rmtree(temp_extract_dir)

        # --------------------------------------------------------
        # NORMAL FILE
        # --------------------------------------------------------
        else:
            file_rows, content_rows = process(temp_file_path)

            for fr in file_rows:
                fr["file_path"] = original_path

            for cr in content_rows:
                cr["file_path"] = original_path

            saved = save_processed_data(db, file_rows, content_rows)
            all_saved_files.extend(saved)
            
            db.commit()
            logger.info(f"Successfully indexed {len(file_rows)} file(s) and {len(content_rows)} chunk(s).")

        # --------------------------------------------------------
        # GENERATE RELATIONSHIPS (For both Zip and Normal files)
        # --------------------------------------------------------
        if all_saved_files:
            for file_obj in all_saved_files:
                generate_file_relationships(source_file_id=file_obj.id, db=db)
        else:
            logger.warning("No content extracted; skipping relationship generation.")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to index {temp_file_path}: {e}")

    finally:
        db.close()
        
        # Cleanup temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Removed temporary file: {temp_file_path}")