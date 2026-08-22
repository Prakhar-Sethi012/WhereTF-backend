from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from .cache import ModelCache

if TYPE_CHECKING:
    from .extractors import ChunkData

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 64

def embed_chunks(
    chunks: list["ChunkData"],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list["ChunkData"]:
    """
    Embeds both text chunks and images using Jina CLIP into the same vector space.
    """
    if not chunks:
        return chunks

    pending_indices = [i for i, c in enumerate(chunks) if "embedding" not in c]
    if not pending_indices:
        return chunks

    model = ModelCache.get_encoder()

    text_indices, image_indices = [], []
    texts, images = [], []

    for i in pending_indices:
        if "content_image" in chunks[i]:
            image_indices.append(i)
            images.append(chunks[i]["content_image"])
        else:
            text_indices.append(i)
            texts.append(chunks[i]["content_text"])

    # 1. Embed text chunks
    if texts:
        text_vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        for list_pos, chunk_idx in enumerate(text_indices):
            chunks[chunk_idx]["embedding"] = text_vectors[list_pos].tolist()

    # 2. Embed image chunks
    if images:
        image_vectors = model.encode(
            images=images,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        for list_pos, chunk_idx in enumerate(image_indices):
            chunks[chunk_idx]["embedding"] = image_vectors[list_pos].tolist()
            del chunks[chunk_idx]["content_image"]

    return chunks