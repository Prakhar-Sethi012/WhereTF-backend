"""
example_usage.py
----------------
Shows how a FastAPI background task / CLI script would call the
processing package and persist results using SQLAlchemy.

This file is NOT part of the processing package itself — it lives
alongside it as reference for the backend team.
"""

# ── SQLAlchemy models (abbreviated) ─────────────────────────────────────────
# from app.models import File, FileContent
# from app.database import SessionLocal

# ── Processing package ───────────────────────────────────────────────────────
from processing import process


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Basic full-directory scan
# ─────────────────────────────────────────────────────────────────────────────

def index_directory(root: str, db) -> None:
    """
    Index every supported file under *root* and persist to the database.

    Parameters
    ----------
    root : str
        Folder or single file path to scan.
    db   : SQLAlchemy Session
        Caller is responsible for lifecycle (commit / rollback / close).
    """
    file_rows, content_rows = process(root)

    # ── Insert File rows ──────────────────────────────────────────────────────
    for fr in file_rows:
        # file_rows keys: file_path, file_hash, mime_type, last_modified, tags
        existing = db.query(File).filter_by(file_path=fr["file_path"]).first()
        if existing:
            # Update hash / timestamp in case the file changed
            for k, v in fr.items():
                setattr(existing, k, v)
        else:
            db.add(File(**fr))

    db.flush()   # ensure File PKs exist before FK inserts

    # ── Insert FileContent rows ───────────────────────────────────────────────
    for cr in content_rows:
        file_path = cr.pop("file_path")   # resolve FK
        file_obj  = db.query(File).filter_by(file_path=file_path).one()

        db.add(FileContent(
            file_id       = file_obj.id,
            chunk_index   = cr["chunk_index"],
            content_text  = cr["content_text"],
            embedding     = cr["embedding"],
            # keyword_tokens is a server-generated TSVECTOR column;
            # PostgreSQL fills it automatically — do not pass it here.
        ))

    db.commit()
    print(f"Indexed {len(file_rows)} file(s), {len(content_rows)} chunk(s).")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Incremental re-index (skip unchanged files)
# ─────────────────────────────────────────────────────────────────────────────

def reindex_directory(root: str, db) -> None:
    """Like index_directory but skips files whose SHA-256 hash is unchanged."""
    existing_hashes = {row.file_hash for row in db.query(File.file_hash).all()}
    file_rows, content_rows = process(root, skip_hashes=existing_hashes)

    for fr in file_rows:
        db.merge(File(**fr))   # upsert on unique file_path

    db.flush()

    for cr in content_rows:
        file_path = cr.pop("file_path")
        file_obj  = db.query(File).filter_by(file_path=file_path).one()
        db.add(FileContent(
            file_id      = file_obj.id,
            chunk_index  = cr["chunk_index"],
            content_text = cr["content_text"],
            embedding    = cr["embedding"],
        ))

    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 3.  FastAPI background task example
# ─────────────────────────────────────────────────────────────────────────────

# from fastapi import BackgroundTasks
#
# @app.post("/index")
# async def trigger_index(path: str, background_tasks: BackgroundTasks):
#     background_tasks.add_task(index_directory, path, SessionLocal())
#     return {"status": "indexing started", "path": path}


# ─────────────────────────────────────────────────────────────────────────────
# 4.  CLI quick-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, pprint
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    file_rows, content_rows = process(root)

    print(f"\n{'='*60}")
    print(f"Files found   : {len(file_rows)}")
    print(f"Chunks created: {len(content_rows)}")
    print(f"{'='*60}\n")

    for cr in content_rows[:3]:
        pprint.pprint({
            "file_path":    cr["file_path"],
            "chunk_index":  cr["chunk_index"],
            "content_text": cr["content_text"][:120] + "…",
            "embedding_dim": len(cr["embedding"]),
        })
