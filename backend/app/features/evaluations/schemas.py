from datetime import datetime

from pydantic import Field

from app.core.schemas import ApiModel


class DimensionScores(ApiModel):
    logic: int = Field(ge=1, le=5)
    appropriateness: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    concision: int = Field(ge=1, le=5)


class EvaluationPayload(ApiModel):
    scores: DimensionScores
    summary: str
    suggestions: list[dict]
    style_tags: list[str]
    evidence: list[dict] = Field(default_factory=list)


class EvidenceDraft(ApiModel):
    dimension: str
    round_no: int = Field(ge=1, le=12)
    quote: str = Field(min_length=4, max_length=240)
    reason: str = Field(min_length=4, max_length=500)
    next_action: str = Field(min_length=4, max_length=300)
    resume_quote: str | None = Field(default=None, max_length=240)


class EvidenceView(ApiModel):
    dimension: str
    round_no: int
    question_message_id: str
    answer_message_id: str
    question: str
    answer: str
    quote: str
    reason: str
    next_action: str
    resume_quote: str | None = None


class EvaluationView(ApiModel):
    id: str
    session_id: str
    scores: DimensionScores
    overall_score: float
    summary: str
    suggestions: list[dict]
    style_tags: list[str]
    created_at: datetime
    degraded: bool = False
    evidence: list[EvidenceView] = Field(default_factory=list)
    plan_id: str | None = None

