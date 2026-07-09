import uuid
from sqlalchemy.sql import func
from sqlalchemy import Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class FileRelationship(Base):
    __tablename__ = "file_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    
    source_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"))
    target_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"))
    
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)

    #  Preventing the duplicate relationship pairs
    __table_args__ = (
        UniqueConstraint('source_file_id', 'target_file_id', name='uq_file_relationship'),
    )