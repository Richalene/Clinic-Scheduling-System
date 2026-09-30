
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables or .env file.
    """
    PROFILE_PICTURE_DIR: str = str(Path(__file__).resolve().parents[1] / "uploads" / "profiles")
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: str
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long.")
        if v.startswith("your_") or v == "placeholder_secret_key_that_is_at_least_32_chars":
            raise ValueError("SECRET_KEY must not be a placeholder value.")
        return v
    
    @property
    def get_allowed_origins_list(self) -> list[str]:
        """Convert comma-separated string to list."""
        origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
        if self.ENVIRONMENT.lower() == "development":
            origins.extend(["http://localhost:5173", "http://127.0.0.1:5173"])
        return list(dict.fromkeys(origins))

settings = Settings()
