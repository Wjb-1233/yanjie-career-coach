from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schemas import ApiModel


Dimension = Literal["logic", "appropriateness", "impact", "relevance", "concision"]


class AbilityAttemptInput(ApiModel):
    evaluation_id: str
    answer: str = Field(min_length=12, max_length=3000)


class AbilityFeedback(ApiModel):
    score: int = Field(ge=1, le=5)
    answer_quote: str = Field(min_length=1, max_length=240)
    strength: str = Field(min_length=4, max_length=500)
    gap: str = Field(min_length=4, max_length=500)
    next_action: str = Field(min_length=4, max_length=300)


class AbilityAttemptView(AbilityFeedback):
    id: str
    answer: str
    created_at: datetime


class AbilityReviewTurn(ApiModel):
    round_no: int
    question: str
    answer: str
    flags: list[str] = Field(default_factory=list)
    is_focus_evidence: bool = False


class AbilityReviewSuggestion(ApiModel):
    round_no: int
    problem: str
    original: str
    rewrite: str


class AbilityPracticeView(ApiModel):
    evaluation_id: str
    session_id: str
    scene_id: str
    scene_title: str
    round_count: int
    overall_score: float
    report_summary: str
    dimension: Dimension
    dimension_label: str
    baseline_score: int
    report_degraded: bool
    question: str
    original_answer: str
    evidence_quote: str | None
    evidence_reason: str | None
    target_action: str
    review_turns: list[AbilityReviewTurn]
    report_suggestions: list[AbilityReviewSuggestion]
    attempts: list[AbilityAttemptView]
