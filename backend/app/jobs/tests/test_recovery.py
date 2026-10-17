import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs.models import Job, JobStage, JobStatus
from app.jobs.worker import recover_interrupted_jobs

ALL_STAGES = (JobStage.CLONE, JobStage.PARSE, JobStage.EMBED, JobStage.SUMMARIZE)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _pipeline(repo_id, statuses: dict) -> list[Job]:
    """Builds all four job rows; stages missing from `statuses` are pending."""
    return [
        Job(
            repository_id=repo_id,
            stage=stage,
            status=statuses.get(stage, JobStatus.PENDING),
            retry_count=2,
            error="old error",
        )
        for stage in ALL_STAGES
    ]


def _mock_db(jobs: list[Job]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = jobs
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


def _by_stage(jobs: list[Job]) -> dict:
    return {JobStage(j.stage): j for j in jobs}


@pytest.mark.anyio
async def test_running_job_with_clone_on_disk_is_reset_alone(tmp_path):
    repo_id = uuid.uuid4()
    (tmp_path / str(repo_id)).mkdir()
    jobs = _pipeline(repo_id, {
        JobStage.CLONE: JobStatus.COMPLETED,
        JobStage.PARSE: JobStatus.COMPLETED,
        JobStage.EMBED: JobStatus.RUNNING,
    })
    db = _mock_db(jobs)

    recovered = await recover_interrupted_jobs(db, tmp_path)

    jobs_by_stage = _by_stage(jobs)
    assert recovered == 1
    assert jobs_by_stage[JobStage.EMBED].status == JobStatus.PENDING
    assert jobs_by_stage[JobStage.EMBED].error is None
    assert jobs_by_stage[JobStage.EMBED].retry_count == 0
    # completed stages and the on-disk clone are untouched
    assert jobs_by_stage[JobStage.CLONE].status == JobStatus.COMPLETED
    assert jobs_by_stage[JobStage.PARSE].status == JobStatus.COMPLETED
    assert (tmp_path / str(repo_id)).is_dir()
    db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_running_clone_job_removes_partial_directory(tmp_path):
    repo_id = uuid.uuid4()
    partial = tmp_path / str(repo_id)
    partial.mkdir()
    (partial / "half-cloned.txt").write_text("partial")
    jobs = _pipeline(repo_id, {JobStage.CLONE: JobStatus.RUNNING})
    db = _mock_db(jobs)

    recovered = await recover_interrupted_jobs(db, tmp_path)

    assert recovered == 1
    assert _by_stage(jobs)[JobStage.CLONE].status == JobStatus.PENDING
    assert not partial.exists()


@pytest.mark.anyio
async def test_missing_clone_directory_restarts_whole_pipeline(tmp_path):
    repo_id = uuid.uuid4()  # no directory created: the disk was wiped
    jobs = _pipeline(repo_id, {
        JobStage.CLONE: JobStatus.COMPLETED,
        JobStage.PARSE: JobStatus.COMPLETED,
        JobStage.EMBED: JobStatus.RUNNING,
    })
    db = _mock_db(jobs)

    recovered = await recover_interrupted_jobs(db, tmp_path)

    assert recovered == 1
    for job in jobs:
        assert job.status == JobStatus.PENDING
        assert job.retry_count == 0
        assert job.error is None


@pytest.mark.anyio
async def test_pipeline_with_failed_job_is_left_alone(tmp_path):
    repo_id = uuid.uuid4()
    jobs = _pipeline(repo_id, {
        JobStage.CLONE: JobStatus.COMPLETED,
        JobStage.PARSE: JobStatus.FAILED,
        JobStage.EMBED: JobStatus.RUNNING,
    })
    db = _mock_db(jobs)

    recovered = await recover_interrupted_jobs(db, tmp_path)

    assert recovered == 0
    assert _by_stage(jobs)[JobStage.PARSE].status == JobStatus.FAILED
    assert _by_stage(jobs)[JobStage.EMBED].status == JobStatus.RUNNING
    db.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_untouched_pending_pipeline_is_left_alone(tmp_path):
    jobs = _pipeline(uuid.uuid4(), {})  # everything still pending, clone not started
    db = _mock_db(jobs)

    recovered = await recover_interrupted_jobs(db, tmp_path)

    assert recovered == 0
    assert all(j.status == JobStatus.PENDING for j in jobs)
    db.commit.assert_not_awaited()