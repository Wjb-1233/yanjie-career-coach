from pydantic import Field

from app.core.schemas import ApiModel
from app.features.scenes.taxonomy import SceneCategory, SceneDifficulty


class UserAdminUpdate(ApiModel):
    role: str | None = Field(default=None, pattern="^(STUDENT|ADMIN)$")
    active: bool | None = None


class SceneAdminInput(ApiModel):
    category: SceneCategory
    title: str = Field(min_length=2, max_length=100)
    industry: str = Field(min_length=2, max_length=60)
    position: str = Field(min_length=2, max_length=80)
    role_name: str = Field(min_length=2, max_length=80)
    difficulty: SceneDifficulty
    background: str = Field(min_length=10, max_length=3000)
    goal: str = Field(min_length=5, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    opening_line: str = Field(min_length=5, max_length=1000)
    active: bool = True


class CourseAdminInput(ApiModel):
    title: str = Field(min_length=2, max_length=120)
    dimension: str = Field(min_length=2, max_length=30)
    minutes: int = Field(ge=1, le=240)
    description: str = Field(min_length=5, max_length=1000)
    content: str = Field(min_length=20, max_length=10000)
    active: bool = True
