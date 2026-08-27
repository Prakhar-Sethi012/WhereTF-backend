"""
pipeline.py
-----------
Top-level orchestrator for the WhereTF processing system.

Call :func:`process` with a folder or file path. It returns two lists
of plain dicts — one per SQLAlchemy model — that your backend can insert
directly without any parsing or transformation:

    file_rows, content_rows = process("/home/user/Documents")

    # Save them:
    for fr in file_rows:
        db.add(File(**fr))

    for cr in content_rows:
        db.add(FileContent(**cr))

    db.commit()

``FileContent`` rows reference their parent ``File`` by ``file_path``
(the unique natural key) so you can look up the FK after inserting
``File`` rows.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .embeddings import embed_chunks
from .extractors import extract
from .traversal import FileEntry, iter_files

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output types (plain dicts — no SQLAlchemy imports here)
# ---------------------------------------------------------------------------

FileRow = dict[str, Any]
"""
{
    "file_path"     : str,
    "file_hash"     : str,
    "mime_type"     : str,
    "last_modified" : datetime,
    "tags"          : list[str],
}
"""

ContentRow = dict[str, Any]
"""
{
    "file_path"   : str,           # FK reference to resolve File ID
    "chunk_index" : int,
    "content_text": str,
    "embedding"   : list[float],   # 384 or 768 dims depending on active tier
}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process(
    root: str | Path,
    embedding_batch_size: int = 64,
    skip_hashes: set[str] | None = None,
) -> tuple[list[FileRow], list[ContentRow]]:
    """
    Walk *root*, extract text (+ embedded images / OCR), embed everything,
    and return two lists of insertion-ready dicts.

    Parameters
    ----------
    root:
        Path to a directory or a single file.
    embedding_batch_size:
        Passed through to :func:`~processing.embeddings.embed_chunks`.
    skip_hashes:
        Optional set of SHA-256 hex digests for files already in the DB.
        Matching files are skipped entirely (incremental indexing).

    Returns
    -------
    file_rows : list[FileRow]
        One dict per discovered file.
    content_rows : list[ContentRow]
        One dict per chunk ready for database insertion.
    """
    skip_hashes = skip_hashes or set()

    file_rows: list[FileRow] = []
    all_chunks: list[dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Phase 1 – Traverse & Extract
    # -------------------------------------------------------------------------
    for entry in iter_files(root):
        file_path: str = entry["file_path"]
        file_hash: str = entry["file_hash"]

        if file_hash in skip_hashes:
            logger.debug("[pipeline] Skipping already-indexed file: %s", file_path)
            continue

        logger.info("[pipeline] Processing: %s", file_path)
        file_rows.append(dict(entry))

        chunks = extract(Path(file_path))
        if not chunks:
            logger.debug("[pipeline] No content extracted from: %s", file_path)
            continue

        for chunk in chunks:
            chunk["_file_path"] = file_path

        all_chunks.extend(chunks)

    if not all_chunks:
        logger.info("[pipeline] No chunks to embed.")
        return file_rows, []

    # -------------------------------------------------------------------------
    # Phase 2 – Batch Embed
    # -------------------------------------------------------------------------
    embed_chunks(all_chunks, batch_size=embedding_batch_size)

    # -------------------------------------------------------------------------
    # Phase 3 – Build ContentRow dicts
    # -------------------------------------------------------------------------
    content_rows: list[ContentRow] = []
    for chunk in all_chunks:
        # Only collect chunks that successfully received embeddings
        if "embedding" in chunk:
            content_rows.append(
                {
                    "file_path":    chunk.pop("_file_path"),
                    "chunk_index":  chunk["chunk_index"],
                    "content_text": chunk["content_text"],
                    "embedding":    chunk["embedding"],
                }
            )

    logger.info(
        "[pipeline] Finished. files=%d  chunks=%d",
        len(file_rows),
        len(content_rows),
    )
    return file_rows, content_rows