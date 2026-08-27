from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "qwen/qwen3.8-27b"
    DATABASE_URL: str = "sqlite:///./finance.db"
    REDIS_URL: str = "redis://localhost:6379"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "convoql"
    LANGCHAIN_TRACING_V2: bool = False  # <-- ADDED
    MAX_RETRIES: int = 3
    READ_ONLY_MODE: bool = True
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # <-- ADDED (ignores unknown .env vars)

@lru_cache()
def get_settings():
    return Settings()