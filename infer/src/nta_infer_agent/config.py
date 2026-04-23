from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INFER_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env", INFER_ENV_FILE, "/etc/infer-agent/env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 9000
    log_level: str = "INFO"

    node_name: str = "h20-node-01"
    agent_token: SecretStr = Field(validation_alias="INFER_AGENT_TOKEN")

    state_path: Path = Path("/var/lib/infer-agent/state.db")
    model_cache_dir: Path = Path("/data/model-cache")
    runtime_dir: Path = Path("/data/nta-runtime")

    docker_bin: str = "docker"
    container_name: str = "nta-vllm"
    default_vllm_image: str = "vllm/vllm-openai:latest"
    vllm_container_port: int = 8000
    max_runtime_restarts: int = Field(
        default=3,
        ge=0,
        validation_alias=AliasChoices("MAX_RUNTIME_RESTARTS", "INFER_MAX_RUNTIME_RESTARTS"),
    )
    runtime_public_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RUNTIME_PUBLIC_HOST", "INFER_RUNTIME_PUBLIC_HOST"),
    )
    huggingface_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_HUB_TOKEN"),
    )
    huggingface_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("HUGGINGFACE_ENDPOINT_URL", "HF_ENDPOINT"),
    )

    reconcile_interval_seconds: float = 2.0
    health_timeout_seconds: int = 900
    health_poll_interval_seconds: float = 2.0

    @field_validator("agent_token")
    @classmethod
    def validate_agent_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if not token:
            raise ValueError("INFER_AGENT_TOKEN must not be empty")
        return SecretStr(token)

    @property
    def model_cache_root(self) -> Path:
        return self.model_cache_dir

    @property
    def runtime_root(self) -> Path:
        return self.runtime_dir


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    return AgentSettings()
