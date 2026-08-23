from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    qdrant_url: str
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    repo_storage_dir: str = "data/repos"
    qdrant_collection_name: str = "code_chunks"

    class Config:
        env_file = ".env"

settings = Settings()