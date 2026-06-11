import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    file_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False) # SHA-256
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    last_modified: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default='{}')

    # Link to the contents table
    contents = relationship("FileContent", back_populates="file", cascade="all, delete-orphan")

    # Indexes from the image
    __table_args__ = (
        Index('files_tags_idx', 'tags', postgresql_using='gin'),
        Index('files_path_hash_idx', 'file_path', 'file_hash'),
    )