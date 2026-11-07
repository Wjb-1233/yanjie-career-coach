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
    source: str = 'builtin'
    visibility: str = 'public'
    mine: bool = False
    favorite: bool = False


class MyScenePayload(ApiModel):
    title: str = Field(min_length=4, max_length=60)
    industry: str = Field(min_length=2, max_length=30)
    position: str = Field(min_length=2, max_length=40)
    role_name: str = Field(min_length=2, max_length=30)
    category: str = Field(default="自定义", max_length=30)
    difficulty: str = Field(default="中级", max_length=10)
    background: str = Field(default="", max_length=500)
    goal: str = Field(default="", max_length=300)
    opening_line: str = Field(default="", max_length=200)
    competency: str | None = Field(default=None, max_length=30)
    tags: list[str] = Field(default_factory=list, max_length=6)
    questions: list[dict] = Field(default_factory=list, min_length=1, max_length=8)
