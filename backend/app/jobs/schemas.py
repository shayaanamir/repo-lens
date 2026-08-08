import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.jobs.models import JobStage, JobStatus


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage: JobStage
    status: JobStatus
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobListResponse(BaseModel):
    repository_id: uuid.UUID
    jobs: list[JobRead]