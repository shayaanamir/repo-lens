import asyncio

from sqlalchemy import select

from app.core.db import async_session_factory
from app.jobs.models import Job
from app.repo.models import Repository  # noqa: F401
from app.analysis.models import Symbol, ImportEdge  # noqa: F401


async def main():
    async with async_session_factory() as db:
        result = await db.execute(select(Job).order_by(Job.created_at))
        for j in result.scalars():
            print(j.stage, j.status, j.error)


if __name__ == "__main__":
    asyncio.run(main())