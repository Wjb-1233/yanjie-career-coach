from pydantic import Field

from app.core.schemas import ApiModel


class QuestionBankStatePatch(ApiModel):
    """只允许改自己的收藏/掌握标记，用户维度由登录态决定。"""

    favorite: bool | None = None
    mastered: bool | None = None


class QuestionBankItem(ApiModel):
    id: str
    scene_id: str
    scene_title: str
    category: str
    text: str = Field(min_length=1, max_length=300)
    dimension: str | None = None
    favorite: bool = False
    mastered: bool = False


class QuestionBankPage(ApiModel):
    items: list[QuestionBankItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20


class DimensionStat(ApiModel):
    dimension: str
    total: int
    mastered: int
    rate: float


class SceneStat(ApiModel):
    scene_id: str
    scene_title: str
    category: str
    total: int
    mastered: int
    rate: float


class QuestionBankSummary(ApiModel):
    total: int
    mastered: int
    favorite: int
    rate: float
    dimensions: list[DimensionStat] = Field(default_factory=list)
    scenes: list[SceneStat] = Field(default_factory=list)
