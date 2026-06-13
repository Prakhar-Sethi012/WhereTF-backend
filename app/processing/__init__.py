"""
processing
----------
WhereTF local-search processing system.

Public surface
~~~~~~~~~~~~~~

    from processing import process

    file_rows, content_rows = process("/path/to/scan")

    # file_rows  → list of dicts matching the `File` SQLAlchemy model
    # content_rows → list of dicts matching the `FileContent` model

Lower-level modules
~~~~~~~~~~~~~~~~~~~
* ``traversal``  – recursive file walker
* ``extractors`` – per-format text + embedded-OCR extractors
* ``ocr``        – EasyOCR singleton wrapper
* ``embeddings`` – batched sentence-transformer inference
* ``pipeline``   – top-level orchestrator (re-exported as ``process``)
"""

from .pipeline import process

__all__ = ["process"]
