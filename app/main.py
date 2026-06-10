from fastapi import FastAPI
app = FastAPI(
    title="WhereTF Backend"
)
@app.get("/")
def root():
    return {"message": "WhereTF Backend is running"}