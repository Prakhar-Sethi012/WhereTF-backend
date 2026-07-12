from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.routes import search
from app.routes import upload
from app.routes import files 
from app.routes import watch
from app.processing.cache import ModelCache  # <-- Import the cache

logger = logging.getLogger(__name__)

# --- THE PRE-WARMER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(" Server booting up. Pre-loading AI models into RAM...")
    ModelCache.get_encoder()
    ModelCache.get_ocr_reader()
    logger.info(" Models loaded successfully. Ready for instant bulk ingestion.")
    
    yield  # The server handles actual user requests here
    
    logger.info("Shutting down server and clearing RAM.")
# ----------------------

app = FastAPI(
    title="WhereTF Backend",
    lifespan=lifespan  # <-- Attach the hook here
)

app.include_router(search.router)
app.include_router(upload.router)
app.include_router(files.router)
app.include_router(watch.router)

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "WhereTF Backend",
        "database_connected": True 
    }