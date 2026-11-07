from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "面试情景模拟训练与话术优化系统"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: str = "sqlite+aiosqlite:///./career_coach.db"
    auto_create_schema: bool = True
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False
    redis_password: SecretStr | None = None

    jwt_secret: str = Field(
        default="development-secret-change-me-at-least-32-characters",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "career-coach-api"
    jwt_audience: str = "career-coach-web"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cookie_domain: str | None = None
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = Field(default=60.0, ge=5.0, le=180.0)
    first_token_timeout_seconds: float = Field(default=18.0, ge=1.0, le=60.0)
    llm_healthcheck_timeout_seconds: float = Field(default=15.0, ge=1.0, le=15.0)
    llm_healthcheck_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    llm_json_mode: bool = True
    lesson_video_dir: str = "static/lessons"
    recording_dir: str = "static/recordings"
    tts_dir: str = "static/tts"
    recording_retention_days: int = Field(default=30, ge=1, le=365)
    recording_janitor_enabled: bool = True
    recording_signing_secret: str = ""
    model_warmup_enabled: bool = True
    task_worker_concurrency: int = Field(default=2, ge=1, le=4)
    # 成本治理：每个学员每天允许的模型调用次数（评分、追问、起草各算一次）
    model_daily_quota: int = Field(default=400, ge=10, le=100000)
    lesson_video_engine: str = "remotion"
    evaluation_samples: int = Field(default=3, ge=1, le=3)
    doubao_realtime_app_id: str = ""
    doubao_realtime_access_token: str = ""
    doubao_realtime_ws_url: str = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"
    doubao_realtime_voice: str = "zh_female_cancan_mars_bigtts"

    # 语音合成（seed-tts-2.0）：与实时对话共用应用凭证，可单独覆盖
    doubao_tts_app_id: str = ""
    doubao_tts_access_token: str = ""
    doubao_tts_speaker: str = "saturn_zh_female_keainvsheng_tob"
    doubao_tts_emotion: str = "gentle"

    milvus_enabled: bool = False
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = "root:Milvus"
    milvus_collection: str = "communication_knowledge"
    milvus_dimension: int = Field(default=384, ge=8, le=32768)

    max_training_rounds: int = Field(default=12, ge=1, le=12)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def empty_cookie_domain(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment != "production":
            return self
        problems: list[str] = []
        if self.jwt_secret == "development-secret-change-me-at-least-32-characters":
            problems.append("JWT_SECRET 不能使用开发默认值")
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL 必须指向生产 MySQL")
        if self.auto_create_schema:
            problems.append("AUTO_CREATE_SCHEMA 必须为 false，生产库应使用 Alembic 迁移")
        if not self.llm_api_key:
            problems.append("LLM_API_KEY 不能为空")
        if not self.redis_enabled:
            problems.append("REDIS_ENABLED 必须为 true")
        if self.redis_password is None or len(self.redis_password.get_secret_value()) < 24:
            problems.append("REDIS_PASSWORD 必须至少包含 24 个字符")
        if not self.milvus_enabled:
            # 向量库缺失只影响课程检索质量，不阻塞启动
            import logging

            logging.getLogger(__name__).warning("production.milvus_disabled 课程检索将降级为关键词匹配")
        if not self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins):
            problems.append("CORS_ORIGINS 必须全部使用 https://")
        if self.cookie_samesite == "none" and self.environment != "production":
            problems.append("SameSite=None 仅允许在安全生产环境使用")
        if problems:
            raise ValueError("生产配置不安全：" + "；".join(problems))
        return self


    @property
    def tts_dir_path(self):
        from pathlib import Path

        path = Path(self.tts_dir)
        return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path

    @property
    def recording_dir_path(self):
        from pathlib import Path

        path = Path(self.recording_dir)
        return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path

    @property
    def lesson_video_dir_path(self):
        from pathlib import Path

        path = Path(self.lesson_video_dir)
        return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

