import logging

logger = logging.getLogger(__name__)

class ModelCache:
    _encoder = None
    _ocr_reader = None

    @classmethod
    def get_encoder(cls):
        if cls._encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("[System] Loading Jina CLIP into RAM...")
                cls._encoder = SentenceTransformer(
                    "jinaai/jina-clip-v1", 
                    trust_remote_code=True
                )
                logger.info("[System] Jina CLIP loaded successfully.")
            except ImportError as exc:
                raise RuntimeError("pip install sentence-transformers einops") from exc
        return cls._encoder

    @classmethod
    def get_ocr_reader(cls, languages=("en",)):
        if cls._ocr_reader is None:
            try:
                import easyocr
                import torch
                gpu_available = torch.cuda.is_available()
                logger.info(f"[System] Loading EasyOCR (gpu={gpu_available})...")
                cls._ocr_reader = easyocr.Reader(list(languages), gpu=gpu_available)
            except ImportError as exc:
                raise RuntimeError("pip install easyocr torch") from exc
        return cls._ocr_reader