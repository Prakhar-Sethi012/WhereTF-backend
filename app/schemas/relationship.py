from uuid import UUID
from pydantic import BaseModel, ConfigDict


class RelationshipBase(BaseModel):
    source_file_id: UUID
    target_file_id: UUID
    similarity_score: float


class RelationshipCreate(RelationshipBase):
    pass


class RelationshipResponse(RelationshipBase):
    id: UUID
    relation_type: str

    model_config = ConfigDict(from_attributes=True)