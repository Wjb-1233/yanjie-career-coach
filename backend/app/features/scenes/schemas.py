from pydantic import Field

from app.core.schemas import ApiModel


class QuestionItem(ApiModel):
    text: str = Field(min_length=2, max_length=300)
    dimension: str | None = Field(default=None, max_length=20)
    difficulty: str | None = Field(default=None, max_length=20)


class SceneView(ApiModel):
    id: str
    category: str
    title: str
    industry: str
    position: str
    role_name: str
    difficulty: str
    background: str
    goal: str
    tags: list[str]
    opening_line: str
    competency: str | None = None
    favorite: bool = False

