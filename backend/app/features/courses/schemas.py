from pydantic import Field

from app.core.schemas import ApiModel


class CourseView(ApiModel):
    id: str
    title: str
    dimension: str
    minutes: int
    description: str
    content: str
    progress: int = 0
    completed: bool = False


class ProgressRequest(ApiModel):
    progress: int = Field(ge=0, le=100)

