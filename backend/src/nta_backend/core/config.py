from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "nta-platform"
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_path: str = "/api/v1"
    secret_key: SecretStr = SecretStr("replace-me")
    access_token_expire_minutes: int = 1440
    auth_auto_login_enabled: bool = True
    auth_session_max_age_seconds: int = 60 * 60 * 24 * 30
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    database_url: str = "postgresql+asyncpg://nta:nta@localhost:5432/nta_platform"
    redis_url: str = "redis://localhost:6379/0"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "nta-platform-dev"
    temporal_task_queue_eval: str = "eval-jobs"
    temporal_task_queue_batch: str = "batch-jobs"
    temporal_task_queue_dataset: str = "dataset-import"

    s3_endpoint_url: str = "http://127.0.0.1:8081"
    s3_browser_endpoint_url: str | None = "http://127.0.0.1:8081"
    s3_region: str = "us-east-1"
    s3_access_key_id: str = "rustfsadmin"
    s3_secret_access_key: SecretStr = SecretStr("ChangeMe123!")
    s3_bucket_main: str = "nta-default"

    @property
    def s3_bucket_dataset_raw(self) -> str:
        return self.s3_bucket_main

    @property
    def s3_bucket_dataset_processed(self) -> str:
        return self.s3_bucket_main

    @property
    def s3_bucket_eval_artifacts(self) -> str:
        return self.s3_bucket_main

    @property
    def s3_bucket_batch_artifacts(self) -> str:
        return self.s3_bucket_main

    @property
    def s3_bucket_exports(self) -> str:
        return self.s3_bucket_main

    @property
    def s3_bucket_tmp(self) -> str:
        return self.s3_bucket_main


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
