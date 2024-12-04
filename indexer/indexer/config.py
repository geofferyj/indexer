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

    # RPC Configuration
    max_rpc_retries: int = 5
    rpc_backoff_factor: float = 0.5
    rpc_rate_limit: int = 100  # Max RPC calls per second

    # Queue Configuration
    max_backlog_size: int = 1000  # Max size of block processing queue

    # Command Configuration
    command_channel: str = "indexer:commands"
    response_channel_prefix: str = "indexer:responses:"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="INDEXER_",
        env_file_encoding="utf-8",
    )


settings = Settings()
