import os
import logging

logger = logging.getLogger(__name__)

class AppConfig:
    TIER = os.getenv("APP_TIER", "pro").lower()

    if TIER == "lite":
        logger.info("[Config] Starting in LITE mode (OCR + MiniLM Text Only)")
        MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
        VECTOR_DIM = 384
        ENABLE_OCR = True
        ENABLE_VISION = False

    elif TIER == "balanced":
        logger.info("[Config] Starting in BALANCED mode (Nomic Vision + Text, No OCR)")
        MODEL_NAME = "nomic-ai/nomic-embed-vision-v1.5" 
        VECTOR_DIM = 768
        ENABLE_OCR = False
        ENABLE_VISION = True

    else:
        logger.info("[Config] Starting in PRO mode (Jina CLIP + OCR)")
        MODEL_NAME = "jinaai/jina-clip-v1"
        VECTOR_DIM = 768
        ENABLE_OCR = True
        ENABLE_VISION = True