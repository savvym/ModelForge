from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class Sample(BaseModel):
    id: str
    input: str | list[ChatMessage]
    target: str | list[str] | None = None
    choices: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


Dataset = list[Sample]
DatasetDict = dict[str, Dataset]
