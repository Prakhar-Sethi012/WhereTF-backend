import uuid
from sqlalchemy import Integer, Text, ForeignKey, Index, Computed
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.sql import func
from app.database import Base

class FileContent(Base):
    __tablename__ = "file_content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"))
    
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # CHANGED: 768 dimensions for Jina CLIP
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    
    # Generated column for Full Text Search
    keyword_tokens = mapped_column(TSVECTOR, Computed("to_tsvector('english', content_text)", persisted=True))

    # Link back to the parent file
    file = relationship("File", back_populates="contents")

    # Indexes from the image
    __table_args__ = (
        Index('content_fts_idx', 'keyword_tokens', postgresql_using='gin'),
        Index('content_embedding_idx', 'embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )