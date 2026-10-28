from datetime import datetime

from pydantic import Field

from app.core.schemas import ApiModel


class GenerateScriptsRequest(ApiModel):
    scene_id: str
    objective: str = Field(min_length=2, max_length=500)
    extra_context: str | None = Field(default=None, max_length=1000)
    original_text: str | None = Field(default=None, max_length=2000)


class ScriptVersion(ApiModel):
    id: str
    scene_id: str | None = None
    created_at: datetime | None = None
    style: str
    content: str
    highlights: list[str] = Field(default_factory=list)
    favorite: bool = False


class ScriptGeneration(ApiModel):
    versions: list[ScriptVersion]
    coach_note: str
    degraded: bool = False

