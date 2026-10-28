import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings


def production_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "mysql+asyncmy://career:secret@mysql:3306/career_coach",
        "auto_create_schema": False,
        "jwt_secret": "a-production-secret-longer-than-32-characters",
        "cors_origins": ["https://coach.example.com"],
        "llm_api_key": "test-key",
        "redis_enabled": True,
        "redis_password": "a-strong-redis-password-32-characters",
        "milvus_enabled": True,
        "_env_file": None,
    }
    values.update(overrides)
    return values


def test_production_rejects_development_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            **production_settings(
                jwt_secret="development-secret-change-me-at-least-32-characters"
            )
        )


def test_production_rejects_insecure_cors_origin() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(**production_settings(cors_origins=["http://coach.example.com"]))


def test_production_rejects_missing_redis_password() -> None:
    with pytest.raises(ValidationError, match="REDIS_PASSWORD"):
        Settings(**production_settings(redis_password=None))


def test_production_rejects_short_redis_password() -> None:
    with pytest.raises(ValidationError, match="REDIS_PASSWORD"):
        Settings(**production_settings(redis_password="too-short"))


def test_cors_origins_accepts_comma_delimited_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://coach.example.com,https://admin.example.com",
    )
    settings = Settings(_env_file=None)
    assert settings.cors_origins == [
        "https://coach.example.com",
        "https://admin.example.com",
    ]


def test_valid_production_settings_pass() -> None:
    settings = Settings(**production_settings())
    assert settings.environment == "production"
    assert settings.auto_create_schema is False


def test_test_suite_uses_disposable_database() -> None:
    assert settings.environment == "test"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
    assert "career-coach-pytest-" in settings.database_url
