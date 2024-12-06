from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL


class Settings(BaseSettings):
    """Settings configuration class for the indexer service."""

    app_name: str = "indexer"

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_username: Optional[str] = None

    @property
    def redis_url(self) -> URL:
        """
        Assemble redis URL from settings.

        :return: redis URL.
        """
        return URL.build(
            scheme="redis",
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            path=f"/{self.redis_db}",
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CONSUMER_",
        env_file_encoding="utf-8",
    )


settings = Settings()
