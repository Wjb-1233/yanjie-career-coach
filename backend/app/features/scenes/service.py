from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.db.models import Favorite, Scene
from app.features.scenes.schemas import SceneView

# 分类 → 岗位能力（与迁移 20261105_0032 的映射保持一致）
COMPETENCY_BY_CATEGORY = {
    "HR 初面": "求职动机与稳定性",
    "HRBP/HR 终面": "求职动机与稳定性",
    "技术一面": "技术深度",
    "技术二面/复面": "技术深度",
    "交叉面/总监面": "协作与影响力",
    "大老板/高管终面": "协作与影响力",
    "基础能力提升": "表达基本功",
}


def competency_of(scene: Scene) -> str:
    return scene.competency or COMPETENCY_BY_CATEGORY.get(scene.category, "沟通表达")


def _with_competency(scene: Scene) -> Scene:
    """老数据没有 competency 时按分类兜底，保证前端永远拿得到能力标签。"""
    if not scene.competency:
        scene.competency = competency_of(scene)
    return scene


async def get_scene(session: AsyncSession, scene_id: str) -> Scene:
    scene = await session.get(Scene, scene_id)
    if scene is None or not scene.active:
        raise not_found("场景")
    return scene


async def list_favorites(session: AsyncSession, user_id: str) -> list[SceneView]:
    scenes = (
        await session.scalars(
            select(Scene).join(Favorite, Favorite.scene_id == Scene.id)
            .where(Favorite.user_id == user_id, Scene.active.is_(True))
            .order_by(Scene.created_at.desc())
        )
    ).all()
    return [SceneView.model_validate(_with_competency(scene)).model_copy(update={"favorite": True}) for scene in scenes]


async def list_scenes(
    session: AsyncSession,
    user_id: str,
    category: str | None,
    industry: str | None,
    position: str | None,
    difficulty: str | None,
    query: str | None,
    page: int,
    size: int,
) -> list[SceneView]:
    favorite_match = and_(Favorite.scene_id == Scene.id, Favorite.user_id == user_id)
    statement = (
        select(Scene, Favorite.user_id.is_not(None).label("favorite"))
        .outerjoin(Favorite, favorite_match)
        .where(Scene.active.is_(True))
    )
    if category:
        statement = statement.where(Scene.category == category)
    if industry:
        statement = statement.where(Scene.industry == industry)
    if position:
        statement = statement.where(Scene.position == position)
    if difficulty:
        statement = statement.where(Scene.difficulty == difficulty)
    if query:
        term = f"%{query.lower()}%"
        statement = statement.where(
            or_(
                func.lower(Scene.title).like(term),
                func.lower(Scene.background).like(term),
                func.lower(Scene.industry).like(term),
                func.lower(Scene.position).like(term),
                func.lower(Scene.role_name).like(term),
            )
        )
    rows = (
        await session.execute(
            statement.order_by(Scene.category, Scene.created_at).offset(page * size).limit(size)
        )
    ).all()
    return [
        SceneView.model_validate(_with_competency(scene)).model_copy(update={"favorite": favorite})
        for scene, favorite in rows
    ]


async def toggle_favorite(session: AsyncSession, user_id: str, scene_id: str) -> bool:
    await get_scene(session, scene_id)
    key = {"user_id": user_id, "scene_id": scene_id}
    favorite = await session.get(Favorite, key)
    if favorite:
        await session.delete(favorite)
        result = False
    else:
        session.add(Favorite(**key))
        result = True
    await session.commit()
    return result

