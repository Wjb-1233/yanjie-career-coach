from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schemas import ApiModel
from app.features.evaluations.schemas import DimensionScores
from app.features.plans.generation import Lesson


class PlanTaskView(ApiModel):
    key: str
    day: int
    task: str
    action_type: Literal["COURSE", "TRAINING", "REWRITE", "RETEST"]
    completed: bool = False
    completed_at: datetime | None = None
    evidence: str | None = None
    course_id: str | None = None
    scene_id: str | None = None
    source_session_id: str | None = None
    lesson: Lesson | None = None
    completed_steps: list[int] = Field(default_factory=list)
    learning_progress: int = 0
    practice_answer: str | None = None
    practice_feedback: str | None = None
    practice_passed: bool = False
    practice_degraded: bool = False
    rewrite_feedback: str | None = None
    rewrite_passed: bool = False
    rewrite_degraded: bool = False


class ScoreComparison(ApiModel):
    baseline_session_id: str
    retest_session_id: str
    scene_id: str
    baseline_scores: DimensionScores
    retest_scores: DimensionScores
    score_deltas: dict[str, int]
    baseline_overall: float
    retest_overall: float
    overall_delta: float
    focus_delta: int
    status: Literal["IMPROVED", "NEEDS_PRACTICE", "PROVISIONAL"]
    recommendation: str


class TrainingPlanView(ApiModel):
    id: str
    title: str
    focus_dimension: str
    status: str
    progress: int
    tasks: list[PlanTaskView]
    comparison: ScoreComparison | None = None
    created_at: datetime


class CompleteTaskRequest(ApiModel):
    evidence: str | None = Field(default=None, max_length=2000)


class PracticeRequest(ApiModel):
    answer: str = Field(min_length=40, max_length=2000)
