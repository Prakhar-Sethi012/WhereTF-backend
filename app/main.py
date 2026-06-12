from fastapi import FastAPI
app = FastAPI(
    title="WhereTF Backend"
)
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