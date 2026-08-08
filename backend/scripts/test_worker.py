import asyncio
import uuid

from sqlalchemy import delete

from app.core.db import async_session_factory
from app.repo.models import Repository
from app.jobs.queue import enqueue_indexing_pipeline

REAL_TEST_URL = "https://github.com/octocat/Hello-World"


async def main():
    async with async_session_factory() as db:
        # Clean up any prior test run using this same URL, so this
        # script stays re-runnable without manual DB cleanup. Cascades
        # to jobs automatically via ondelete='CASCADE'.
        await db.execute(delete(Repository).where(Repository.github_url == REAL_TEST_URL))
        await db.commit()

        repo = Repository(
            id=uuid.uuid4(),
            github_url=REAL_TEST_URL,
            name=f"Hello-World-{uuid.uuid4().hex[:8]}",
            default_branch="master",
            status="pending",
        )
        db.add(repo)
        await db.commit()
        await db.refresh(repo)

        print(f"Created repository: {repo.id}")

        jobs = await enqueue_indexing_pipeline(db, repo.id)
        print(f"Enqueued {len(jobs)} jobs:")
        for job in jobs:
            print(f"  - stage={job.stage}, status={job.status}")


if __name__ == "__main__":
    asyncio.run(main())