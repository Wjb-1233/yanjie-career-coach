from app.core.schemas import ApiModel


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
    favorite: bool = False

