import uuid

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Symbol(Base):
    __tablename__ = "symbol"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Denormalized for fast repo-scoped queries without joining through `file`
    # (ARCHITECTURE.md §15: index repository_id across file/symbol/import_edge)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # function, class, method...
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    file: Mapped["File"] = relationship(back_populates="symbols")


class ImportEdge(Base):
    __tablename__ = "import_edge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    target_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    source_file: Mapped["File"] = relationship(foreign_keys=[source_file_id])
    target_file: Mapped["File"] = relationship(foreign_keys=[target_file_id])