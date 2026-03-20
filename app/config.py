"""
Configuration module — loads settings from .env file.
Uses Pydantic Settings for type-safe environment variable management.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    # --- Application ---
    APP_NAME: str = "True Capability Validator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # --- File Upload ---
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # --- Database ---
    DATABASE_PATH: str = "./data/validator.db"

    # --- API Keys ---
    GITHUB_TOKEN: str = ""
    GEMINI_API_KEY: str = ""

    # --- Scraping ---
    REQUEST_TIMEOUT: int = 15  # seconds
    MAX_CONCURRENT_SCRAPES: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Allow extra env vars without crashing

    @property
    def upload_path(self) -> Path:
        """Resolved upload directory path, created on access."""
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        """Resolved database file path, parent dir created on access."""
        path = Path(self.DATABASE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


# Singleton instance — import this throughout the app
settings = Settings()
