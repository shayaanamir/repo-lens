import asyncio
import uuid

from app.core.db import async_session_factory
from app.repo.models import Repository
from app.jobs.queue import enqueue_indexing_pipeline


async def main():
    async with async_session_factory() as db:
        unique_suffix = uuid.uuid4().hex[:8]
        repo = Repository(
            id=uuid.uuid4(),
            github_url=f"https://github.com/octocat/Hello-World-{unique_suffix}",
            name=f"Hello-World-{unique_suffix}",
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