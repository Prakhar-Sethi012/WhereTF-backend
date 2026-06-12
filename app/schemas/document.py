from pydantic import BaseModel


class DocumentIngest(BaseModel):
    file_path: str
    raw_text: str
class DocumentSearchResponse(BaseModel):
    filename: str
    file_path: str
    snippet: str
    score: float