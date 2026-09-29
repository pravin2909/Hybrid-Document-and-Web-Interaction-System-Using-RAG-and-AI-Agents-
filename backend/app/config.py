from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LM Studio
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    lmstudio_api_key: str = "lm-studio"
    chat_model: str = "google/gemma-4-e4b"
    embedding_model: str = "text-embedding-bge-small-en-v1.5"
    embedding_batch_size: int = 64
    lmstudio_timeout: float = 180.0

    # Agent
    agent_max_steps: int = 6
    agent_temperature: float = 0.2

    # Retrieval
    chroma_dir: str = "./data/chroma"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    retrieval_top_k: int = 6
    rrf_k: int = 60

    # Web search
    web_search_provider: str = "auto"
    web_search_results: int = 5
    http_timeout: float = 15.0
    tavily_api_key: str = ""
    searxng_url: str = ""

    # Database (Postgres)
    database_url: str = "postgresql://localhost:5432/agentic_rag"

    # Server / uploads
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
