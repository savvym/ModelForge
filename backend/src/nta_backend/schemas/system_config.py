from pydantic import BaseModel, Field


class SystemHuggingFaceSettings(BaseModel):
    endpoint_url: str | None = None
    token: str | None = None
    has_token: bool = False


class SystemHuggingFaceSettingsUpdate(BaseModel):
    endpoint_url: str | None = Field(default=None, max_length=500)
    token: str | None = Field(default=None, max_length=4000)
    clear_token: bool = False


class SystemTrainingCosSettings(BaseModel):
    enabled: bool = False
    protocol: str = "http"
    endpoint: str | None = None
    endpoint_url: str | None = None
    region: str | None = None
    bucket: str | None = None
    bucket_alias: str | None = None
    target_prefix: str | None = None
    addressing_style: str = "virtual"
    hosts: str | None = None
    has_secret_id: bool = False
    has_secret_key: bool = False
    has_session_token: bool = False
    secret_id_masked: str | None = None
    secret_key_masked: str | None = None
    session_token_masked: str | None = None


class SystemTrainingCosSettingsUpdate(BaseModel):
    enabled: bool = False
    protocol: str | None = Field(default="http", max_length=16)
    endpoint: str | None = Field(default=None, max_length=500)
    region: str | None = Field(default=None, max_length=120)
    bucket: str | None = Field(default=None, max_length=255)
    bucket_alias: str | None = Field(default=None, max_length=120)
    target_prefix: str | None = Field(default=None, max_length=500)
    addressing_style: str | None = Field(default="virtual", max_length=32)
    hosts: str | None = Field(default=None, max_length=8000)
    secret_id: str | None = Field(default=None, max_length=1000)
    secret_key: str | None = Field(default=None, max_length=4000)
    session_token: str | None = Field(default=None, max_length=4000)
    clear_secret_id: bool = False
    clear_secret_key: bool = False
    clear_session_token: bool = False


class SystemTrainingCosProbeResponse(BaseModel):
    ok: bool
    message: str
    bucket: str | None = None
    prefix: str | None = None
    object_count: int | None = None
