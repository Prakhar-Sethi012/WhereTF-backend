from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from .cache import ModelCache
from app.config import AppConfig
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
            if AppConfig.ENABLE_VISION:
                # Pro / Balanced Tier: Keep the image for Jina CLIP
                image_indices.append(i)
                images.append(chunks[i]["content_image"])
            else:
                # Lite Tier: Throw away the image, Jina CLIP isn't loaded!
                del chunks[i]["content_image"]
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
        # Dynamically hunt down the underlying Jina CLIP AutoModel inside the wrapper
        jina_hf_model = next((m for m in model.modules() if hasattr(m, "encode_image")), None)
        
        if not jina_hf_model:
            raise RuntimeError("Could not find the Jina Vision encoder inside the model!")
            
        import torch
        import numpy as np
        
        # Disable gradients to save RAM during the forward pass
        with torch.no_grad():
            image_vectors = jina_hf_model.encode_image(images)
            
        # Convert to a numpy array if it returned a PyTorch tensor
        if isinstance(image_vectors, torch.Tensor):
            image_vectors = image_vectors.cpu().numpy()
            
        # Normalize the vectors to ensure cosine similarity matches the text vectors
        norms = np.linalg.norm(image_vectors, axis=1, keepdims=True)
        image_vectors = image_vectors / np.maximum(norms, 1e-12)

        for list_pos, chunk_idx in enumerate(image_indices):
            chunks[chunk_idx]["embedding"] = image_vectors[list_pos].tolist()
            del chunks[chunk_idx]["content_image"]

    return chunks