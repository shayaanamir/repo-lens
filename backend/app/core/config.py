from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    qdrant_url: str
    qdrant_api_key: str = ""
    # "local" = FastEmbed on this machine, "qdrant_cloud" = Qdrant Cloud Inference
    embedding_provider: str = "local"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    repo_storage_dir: str = "data/repos"
    qdrant_collection_name: str = "code_chunks"
    cors_origins: str = "http://localhost:3000"  # comma-separated list
    rate_limiting_enabled: bool = True
    max_repositories: int = 0          # 0 = unlimited (local dev)
    admin_token: str = ""              # empty = delete is open (local dev)
    ai_global_hourly_limit: int = 0    # 0 = unlimited (local dev)

    class Config:
        env_file = ".env"

settings = Settings()