from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.database.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)

    # pgvector embedding (we'll generate later)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))