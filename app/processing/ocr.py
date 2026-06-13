"""
ocr.py
------
Thin, lazy-initialised wrapper around EasyOCR.

Design goals
~~~~~~~~~~~~
* One global reader instance (EasyOCR is expensive to initialise).
* Accepts raw ``bytes`` so callers never need to touch the filesystem.
* Returns a single cleaned string; empty string on failure.
* GPU is used when available; falls back to CPU silently.
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache
from typing import Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_reader(languages: tuple[str, ...] = ("en",)):
    """
    Initialise and cache a single EasyOCR Reader.

    The tuple argument is required so that lru_cache can hash it.
    Import is deferred so the module loads fast even when EasyOCR is
    installed but not yet needed.
    """
    try:
        import easyocr  # type: ignore
        logger.info("[ocr] Initialising EasyOCR (languages=%s) …", languages)
        return easyocr.Reader(list(languages), gpu=_gpu_available())
    except ImportError as exc:
        raise RuntimeError(
            "EasyOCR is required for embedded image OCR. "
            "Install it with:  pip install easyocr"
        ) from exc


def _gpu_available() -> bool:
    try:
        import torch  # type: ignore
        return torch.cuda.is_available()
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ocr_image_bytes(
    image_bytes: bytes,
    languages: Sequence[str] = ("en",),
) -> str:
    """
    Run EasyOCR on *image_bytes* and return the extracted text.

    Parameters
    ----------
    image_bytes:
        Raw bytes of any image format supported by EasyOCR
        (PNG, JPEG, WEBP, BMP, TIFF, …).
    languages:
        ISO-639-1 language codes to pass to EasyOCR.

    Returns
    -------
    str
        Whitespace-joined OCR result, or ``""`` if nothing was detected
        or an error occurred.
    """
    if not image_bytes:
        return ""

    try:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore

        reader = _get_reader(tuple(languages))

        # Convert bytes → PIL → numpy (EasyOCR accepts numpy arrays natively)
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        np_img = np.array(pil_img)

        results = reader.readtext(np_img, detail=0, paragraph=True)
        return " ".join(results).strip()

    except Exception as exc:  # noqa: BLE001
        logger.warning("[ocr] Failed to OCR image chunk (%d bytes): %s", len(image_bytes), exc)
        return ""
