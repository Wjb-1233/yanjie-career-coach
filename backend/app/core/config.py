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
            problems.append("MILVUS_ENABLED 必须为 true")
        if not self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins):
            problems.append("CORS_ORIGINS 必须全部使用 https://")
        if self.cookie_samesite == "none" and self.environment != "production":
            problems.append("SameSite=None 仅允许在安全生产环境使用")
        if problems:
            raise ValueError("生产配置不安全：" + "；".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

