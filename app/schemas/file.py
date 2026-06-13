from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FileBase(BaseModel):
    file_path: str


class FileCreate(FileBase):
    pass


class FileResponse(BaseModel):
    id: UUID

    file_path: str
    file_hash: str

    mime_type: str

    last_modified: datetime

    indexed_at: datetime

    tags: list[str]

    model_config = ConfigDict(from_attributes=True)