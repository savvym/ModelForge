from pydantic import BaseModel, Field


class SystemHuggingFaceSettings(BaseModel):
    endpoint_url: str | None = None
    token: str | None = None
    has_token: bool = False


class SystemHuggingFaceSettingsUpdate(BaseModel):
    endpoint_url: str | None = Field(default=None, max_length=500)
    token: str | None = Field(default=None, max_length=4000)
    clear_token: bool = False
