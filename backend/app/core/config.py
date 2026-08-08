from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    qdrant_url: str
    gemini_api_key: str = ""
    repo_storage_dir: str = "data/repos"  # persistent clones live here

    class Config:
        env_file = ".env"

settings = Settings()