from pydantic import AnyUrl
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal

class Settings(BaseSettings):
    ENV: str = "dev"
    REDIS_URL: AnyUrl | None = None
    SERVICE_PORT: int = 8080
    MAX_EVENT_SIZE: int = 65536
    LOG_JSON: bool = True
    # Backend adapter selection: "memory" or "redis"
    BUS_ADAPTER: Literal["memory", "redis"] = "memory"
    # Authentication
    API_KEYS: str = ""  # Comma-separated list of API keys
    REQUIRE_AUTH: bool = False  # Whether to enforce authentication

    class ConfigDict:
        env_file = ".env"
        extra = "ignore"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
