from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

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

    database_url: str = "postgresql+asyncpg://nta:nta@localhost:5432/model_forge"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "nta-platform-dev"
    temporal_task_queue_eval: str = "eval-jobs"
    temporal_task_queue_batch: str = "batch-jobs"
    temporal_task_queue_dataset: str = "dataset-import"
    probe_registration_token: SecretStr | None = None
    probe_heartbeat_timeout_seconds: int = 90
    probe_task_claim_ttl_seconds: int = 300

    s3_endpoint_url: str = "http://127.0.0.1:8081"
    s3_browser_endpoint_url: str | None = "http://127.0.0.1:8081"
    s3_region: str = "us-east-1"
    s3_addressing_style: Literal["auto", "path", "virtual"] = "path"
    s3_access_key_id: str = "rustfsadmin"
    s3_secret_access_key: SecretStr = SecretStr("ChangeMe123!")
    s3_bucket_main: str = "nta-default"
    s3_root_prefix: str | None = None
    s3_direct_upload_mode: Literal["auto", "presigned", "cos-sts"] = "auto"
    s3_sts_duration_seconds: int = 1800

    @property
    def s3_resolved_root_prefix(self) -> str:
        normalized = (self.s3_root_prefix or "").strip().strip("/")
        if normalized:
            return normalized
        if self.app_env == "production":
            return "nta-prod"
        return "nta-dev"

    @property
    def s3_resolved_direct_upload_mode(self) -> Literal["presigned", "cos-sts"]:
        if self.s3_direct_upload_mode != "auto":
            return self.s3_direct_upload_mode

        endpoint = self.s3_browser_endpoint_url or self.s3_endpoint_url
        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        host = (parsed.netloc or parsed.path).lower()
        if host.endswith("myqcloud.com") or host.endswith("tencentcos.cn"):
            return "cos-sts"
        return "presigned"

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

    infer_agent_base_url: str | None = None
    infer_agent_token: SecretStr | None = None
    infer_runtime_public_host: str | None = None
    infer_object_storage_endpoint_url: str | None = None
    infer_vllm_image: str = "vllm/vllm-openai:latest"
    infer_default_gpu_ids: str = "0,1,2,3,4,5,6,7"
    infer_default_tensor_parallel_size: int = 8
    infer_default_dtype: str = "bfloat16"
    infer_default_gpu_memory_utilization: float = 0.85
    infer_default_max_model_len: int | None = None
    infer_default_listen_port: int = 8000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
