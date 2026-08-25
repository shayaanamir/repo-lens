import asyncio
import shutil
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.db import async_session_factory
from app.repo.models import Repository
from app.jobs.models import Job  # noqa: F401
from app.analysis.models import Symbol, ImportEdge  # noqa: F401
from app.search.qdrant_client import delete_repository_vectors


async def main():
    async with async_session_factory() as db:
        repo_ids = (await db.execute(select(Repository.id))).scalars().all()

        for repo_id in repo_ids:
            await delete_repository_vectors(repo_id)
            shutil.rmtree(Path(settings.repo_storage_dir) / str(repo_id), ignore_errors=True)

        result = await db.execute(delete(Repository))
        await db.commit()
        print(f"Deleted {result.rowcount} repositories (jobs/symbols/edges cascaded, Qdrant + disk cleaned)")


if __name__ == "__main__":
    asyncio.run(main())