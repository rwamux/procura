import os
import re

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Accepts any postgres URL format: postgres://, postgresql://, or with +driver suffix.
    # The validator normalises both variants so callers always get the right driver prefix.
    DATABASE_URL: str
    DATABASE_URL_SYNC: str = ""  # derived from DATABASE_URL if not set explicitly

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    OPENROUTER_API_KEY: str
    APP_URL: str = "http://localhost:3000"
    UPLOAD_DIR: str = "uploads"
    DEBUG: bool = False

    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "procura"

    @model_validator(mode="after")
    def _normalise_db_urls(self) -> "Settings":
        base = re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql://", self.DATABASE_URL)
        self.DATABASE_URL = base.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not self.DATABASE_URL_SYNC:
            self.DATABASE_URL_SYNC = base.replace("postgresql://", "postgresql+psycopg://", 1)
        return self


settings = Settings()

# LangChain reads these directly from os.environ, not from the settings object
if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
