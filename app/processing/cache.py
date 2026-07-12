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
                logger.info("[System] Loading Sentence Transformer into RAM...")
                #  loading it exactly once here
                cls._encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                logger.info("[System] Sentence Transformer loaded successfully.")
            except ImportError as exc:
                raise RuntimeError("pip install sentence-transformers") from exc
        return cls._encoder

    @classmethod
    def get_ocr_reader(cls, languages=("en",)):
        if cls._ocr_reader is None:
            try:
                import easyocr
                import torch
                # Safely check for GPU, otherwise fallback to CPU
                gpu_available = torch.cuda.is_available()
                logger.info(f"[System] Loading EasyOCR into RAM (gpu={gpu_available})...")
                cls._ocr_reader = easyocr.Reader(list(languages), gpu=gpu_available)
                logger.info("[System] EasyOCR loaded successfully.")
            except ImportError as exc:
                raise RuntimeError("pip install easyocr torch") from exc
        return cls._ocr_reader