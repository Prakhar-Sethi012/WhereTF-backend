import uuid
from sqlalchemy import Float, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class FileRelationship(Base):
    __tablename__ = "file_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    source_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"))
    target_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"))
    
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), server_default='semantic_similarity')

    __table_args__ = (
        UniqueConstraint('source_file_id', 'target_file_id', name='uq_file_relationship'),
    )