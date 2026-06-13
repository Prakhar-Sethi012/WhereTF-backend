"""
processing
----------
WhereTF local-search processing system.

Public surface
~~~~~~~~~~~~~~

Indexing (ingestion side)
    from processing import process

    file_rows, content_rows = process("/path/to/scan")

    # file_rows     → list of dicts matching the `File`        SQLAlchemy model
    # content_rows  → list of dicts matching the `FileContent` SQLAlchemy model

Searching (query side)
    from processing.search import build_query, query_vector

    payload = build_query("JWT authentication", mode="hybrid", top_k=10)
    # payload["sql"]["hybrid"]  → parametrised SQL string
    # payload["params"]         → bind-param dict for session.execute()
    # payload["vector"]         → 384-dim list[float]

    vec = query_vector("what is time management")  # just the embedding

Modules
~~~~~~~
* ``traversal``  – recursive file walker → FileEntry dicts
* ``extractors`` – per-format text + embedded-OCR extractors, rolling chunker
* ``ocr``        – lazy EasyOCR singleton (GPU-aware)
* ``embeddings`` – batched sentence-transformer inference
* ``pipeline``   – top-level orchestrator  (re-exported as ``process``)
* ``search``     – query embedding + SQL builder for vector/keyword/hybrid search

See ``BACKEND_INTEGRATION.md`` for the full setup guide.
"""

from .pipeline import process
from .search   import build_query, query_vector

__all__ = ["process", "build_query", "query_vector"]