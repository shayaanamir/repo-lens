from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """All ORM models inherit from this. Alembic also points at
    Base.metadata to auto-detect model changes for migrations."""
    pass


engine = create_async_engine(settings.database_url, echo=True)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    """FastAPI dependency: yields a DB session per-request, closes it after."""
    async with async_session_factory() as session:
        yield session