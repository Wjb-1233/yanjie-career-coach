from datetime import datetime

from pydantic import Field

from app.core.schemas import ApiModel


class CreateSessionRequest(ApiModel):
    scene_id: str


class SendMessageRequest(ApiModel):
    content: str = Field(min_length=1, max_length=2000)
    finish_after_reply: bool = False


class MessageView(ApiModel):
    id: str
    round_no: int
    speaker: str
    content: str
    flagged: bool
    flags: list[str]
    created_at: datetime


class TurnReplyView(ApiModel):
    round_no: int
    stage: str
    flags: list[str]
    message_id: str
    content: str
    finished: bool
    degraded: bool


class SessionView(ApiModel):
    id: str
    scene_id: str
    scene_title: str | None = None
    status: str
    stage: str
    current_round: int
    max_rounds: int
    started_at: datetime
    finished_at: datetime | None
    archived_at: datetime | None = None
    resume_filename: str | None = None
    resume_opening_degraded: bool = False
    messages: list[MessageView] = Field(default_factory=list)


class TrainingHistoryItem(ApiModel):
    id: str
    scene_id: str
    scene_title: str
    status: str
    current_round: int
    max_rounds: int
    started_at: datetime
    finished_at: datetime | None
    overall_score: float | None = None
    evaluation_degraded: bool = False
    archived_at: datetime | None = None

