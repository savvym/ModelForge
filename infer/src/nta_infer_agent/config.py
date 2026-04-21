from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "/etc/infer-agent/env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 9000
    log_level: str = "INFO"

    node_name: str = "h20-node-01"
    agent_token: SecretStr | None = None

    state_path: Path = Path("/var/lib/infer-agent/state.db")
    model_cache_dir: Path = Path("/data/model-cache")
    runtime_dir: Path = Path("/data/nta-runtime")

    docker_bin: str = "docker"
    container_name: str = "nta-vllm"
    default_vllm_image: str = "vllm/vllm-openai:latest"
    vllm_container_port: int = 8000
    runtime_public_host: str | None = None
    huggingface_token: SecretStr | None = None
    huggingface_endpoint_url: str | None = None

    reconcile_interval_seconds: float = 2.0
    health_timeout_seconds: int = 900
    health_poll_interval_seconds: float = 2.0

    @property
    def model_cache_root(self) -> Path:
        return self.model_cache_dir

    @property
    def runtime_root(self) -> Path:
        return self.runtime_dir


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    return AgentSettings()
