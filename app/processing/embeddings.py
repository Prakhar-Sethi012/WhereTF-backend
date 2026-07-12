"""
embeddings.py
-------------
Batched embedding pipeline for WhereTF.

Takes a flat list of ``ChunkData`` dicts (produced by the extractors) and
mutates each one in-place by adding an ``"embedding"`` key whose value is a
plain Python ``list[float]`` of 384 dimensions — ready to be passed straight
into the ``FileContent`` SQLAlchemy model.

The model is loaded once and cached for the lifetime of the process.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cache import ModelCache  # <-- Importing our new Singleton

if TYPE_CHECKING:
    from .extractors import ChunkData

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 64


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_chunks(
    chunks: list["ChunkData"],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list["ChunkData"]:
    """
    Add an ``"embedding"`` field to every chunk dict **in-place** and
    return the same list for convenient chaining.

    Parameters
    ----------
    chunks:
        Output of :func:`~processing.extractors.extract` — one dict per
        text chunk.  Dicts that already have an ``"embedding"`` key are
        skipped so this function is safe to call multiple times.
    batch_size:
        Number of texts to encode per forward pass.  64 is a good default
        for CPU; increase to 256+ when a GPU is available.

    Returns
    -------
    list[ChunkData]
        The same list, each dict now containing:
        ``{"chunk_index": int, "content_text": str, "embedding": list[float]}``
    """
    if not chunks:
        return chunks

    # Separate chunks that still need embeddings
    pending_indices = [i for i, c in enumerate(chunks) if "embedding" not in c]
    if not pending_indices:
        return chunks

    # grabs the model from RAM using singleton
    model = ModelCache.get_encoder()
    texts = [chunks[i]["content_text"] for i in pending_indices]

    logger.info(
        "[embeddings] Encoding %d chunk(s) in batches of %d …",
        len(texts),
        batch_size,
    )

    # encode() returns a numpy array of shape (N, 384)
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,   # unit-normalised → cosine ≡ dot product
    )

    for list_pos, chunk_idx in enumerate(pending_indices):
        # Store as plain Python list[float] — JSON-serialisable, pgvector-ready
        chunks[chunk_idx]["embedding"] = vectors[list_pos].tolist()

    logger.info("[embeddings] Done.")
    return chunks