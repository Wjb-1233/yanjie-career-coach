"""故事库的请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.schemas import ApiModel


class StoryPayload(ApiModel):
    title: str = Field(min_length=2, max_length=40)
    situation: str = ""
    task: str = ""
    action: str = Field(min_length=10, max_length=600)
    result: str = ""
    tags: list[str] = Field(default_factory=list)


class StoryUpdate(ApiModel):
    title: str | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    tags: list[str] | None = None


class StoryView(ApiModel):
    id: str
    title: str
    situation: str
    task: str
    action: str
    result: str
    tags: list[str]
    source_session_id: str | None = None
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class ExtractRequest(ApiModel):
    session_id: str
