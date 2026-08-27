import logging
from app.config import AppConfig

logger = logging.getLogger(__name__)

class ModelCache:
    _encoder = None
    _ocr_reader = None

    @classmethod
    def get_encoder(cls):
        if cls._encoder is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"[System] Loading {AppConfig.MODEL_NAME} into RAM...")
            cls._encoder = SentenceTransformer(
                AppConfig.MODEL_NAME, 
                trust_remote_code=True
            )
        return cls._encoder

    @classmethod
    def get_ocr_reader(cls, languages=("en",)):
        # If the active tier disables OCR, never load it into RAM
        if not AppConfig.ENABLE_OCR:
            return None

        if cls._ocr_reader is None:
            import easyocr
            import torch
            gpu_available = torch.cuda.is_available()
            logger.info(f"[System] Loading EasyOCR (gpu={gpu_available})...")
            cls._ocr_reader = easyocr.Reader(list(languages), gpu=gpu_available)
            
        return cls._ocr_reader