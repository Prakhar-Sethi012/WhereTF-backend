from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ContentBase(BaseModel):
    file_id: UUID

    chunk_index: int

    content_text: str


class ContentCreate(ContentBase):
    pass


class ContentResponse(ContentBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)