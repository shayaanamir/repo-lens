from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RepositoryCreate(BaseModel):
    github_url: str = Field(..., examples=["https://github.com/facebook/react"])


class RepositoryOut(BaseModel):
    id: UUID
    github_url: str
    name: str
    default_branch: str
    status: str
    primary_language: str | None
    readme_content: str | None
    summary: str | None
    imported_at: datetime

    class Config:
        from_attributes = True  # lets this be built directly from a SQLAlchemy object


class FileOut(BaseModel):
    id: UUID
    path: str
    language: str | None
    size: int

    class Config:
        from_attributes = True


class FileContentOut(BaseModel):
    path: str
    content: str

class StageStatOut(BaseModel):
    stage: str
    status: str
    detail: str | None


class LanguageStatOut(BaseModel):
    language: str
    percentage: float


class ModuleStatOut(BaseModel):
    path: str
    symbol_count: int
    in_degree: int
    out_degree: int
    start_line: int | None
    end_line: int | None


class RepositoryStatsOut(BaseModel):
    file_count: int
    total_size_bytes: int
    symbol_count: int
    edge_count: int
    chunk_count: int
    vector_dim: int
    languages: list[LanguageStatOut]
    stages: list[StageStatOut]
    modules: list[ModuleStatOut]
    completed_at: datetime | None
    duration_seconds: float | None