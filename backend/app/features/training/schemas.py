from datetime import datetime

from pydantic import Field

from app.core.schemas import ApiModel


class CreateSessionRequest(ApiModel):
    scene_id: str
    mode: str = Field(default="STANDARD", pattern="^(STANDARD|DRILL)$")
    depth: str = Field(default="STANDARD", pattern="^(STANDARD|THREE_LAYER|PRESSURE)$")
    plan_id: str | None = None
    task_key: str | None = None


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


class MessageRewriteView(ApiModel):
    round_no: int
    original: str
    rewrite: str
    reason: str
    flags: list[str] = Field(default_factory=list)
    degraded: bool = False


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
    channel: str = "TEXT"
    mode: str = "STANDARD"
    depth: str = "STANDARD"
    duration_seconds: int | None = None
    delivery: dict | None = None
    recording_url: str | None = None
    started_at: datetime
    finished_at: datetime | None
    archived_at: datetime | None = None
    resume_filename: str | None = None
    resume_opening_degraded: bool = False
    jd_text: str | None = None
    job_match: dict | None = None
    question_plan: list[dict] = Field(default_factory=list)
    question_total: int = 0
    question_covered: int = 0
    messages: list[MessageView] = Field(default_factory=list)


class TrainingHistoryItem(ApiModel):
    id: str
    channel: str = "TEXT"
    delivery: dict | None = None
    recording_url: str | None = None
    duration_seconds: int | None = None
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


class SelfReviewItem(ApiModel):
    round_no: int = Field(ge=1, le=12)
    camera: bool = False
    structure: bool = False
    opening: bool = False
    note: str | None = Field(default=None, max_length=200)


class SelfReviewRequest(ApiModel):
    items: list[SelfReviewItem] = Field(default_factory=list, max_length=12)


class TranscriptEditRequest(ApiModel):
    text: str = Field(min_length=1, max_length=2000)
