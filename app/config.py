from pydantic import BaseSettings, AnyUrl
from functools import lru_cache

class Settings(BaseSettings):
    ENV: str = "dev"
    REDIS_URL: AnyUrl | None = None
    SERVICE_PORT: int = 8080
    MAX_EVENT_SIZE: int = 65536
    LOG_JSON: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
