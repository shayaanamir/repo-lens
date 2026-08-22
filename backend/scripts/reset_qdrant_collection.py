# backend/scripts/reset_qdrant_collection.py
import asyncio

from app.core.config import settings
from app.search.qdrant_client import ensure_collection, get_qdrant_client


async def main():
    client = get_qdrant_client()
    if await client.collection_exists(settings.qdrant_collection_name):
        await client.delete_collection(settings.qdrant_collection_name)
        print(f"Deleted collection '{settings.qdrant_collection_name}'")
    await ensure_collection()


if __name__ == "__main__":
    asyncio.run(main())