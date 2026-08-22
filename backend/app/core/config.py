from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    qdrant_url: str
    gemini_api_key: str = ""
    repo_storage_dir: str = "data/repos"
    qdrant_collection_name: str = "code_chunks"  # shared collection, filtered by repository_id payload

    class Config:
        env_file = ".env"

settings = Settings()