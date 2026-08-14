import asyncio

from sqlalchemy import delete

from app.core.db import async_session_factory
from app.repo.models import Repository
from app.jobs.models import Job  # noqa: F401
from app.analysis.models import Symbol, ImportEdge  # noqa: F401


async def main():
    async with async_session_factory() as db:
        result = await db.execute(delete(Repository))
        await db.commit()
        print(f"Deleted {result.rowcount} repositories (jobs/symbols/edges cascaded)")


if __name__ == "__main__":
    asyncio.run(main())