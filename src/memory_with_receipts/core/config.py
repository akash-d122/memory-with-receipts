from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Defaults are test/local safe. Real deployment values should come from environment variables.
    New RAG-related settings have safe defaults that do not break existing tests.
    """

    # Core
    app_name: str = "Memory With Receipts"
    environment: str = "test"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/memory_with_receipts"

    # LLM provider
    llm_provider: str = "mock"
    llm_model: str = "gemini-2.0-flash"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Embedding provider
    embedding_provider: str = "mock"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Chunking
    chunking_strategy: str = "structure_aware"
    chunk_size: int = 512
    chunk_overlap: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
