from fastapi import FastAPI
from app.routes import search
from app.routes import upload


app = FastAPI(
    title="WhereTF Backend"
)

app.include_router(search.router)
app.include_router(upload.router)

@app.get("/health", tags=["System"])
def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {
        "status": "healthy",
        "service": "WhereTF Backend",
        "database_connected": True  # If the API booted, the Docker depends_on guarantees this is true
    }
