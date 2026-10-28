import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.llm import LlmGateway


def llm_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "llm_api_key": "test-key",
        "llm_base_url": "https://llm.example.com",
        "llm_model": "test-model",
        "llm_healthcheck_timeout_seconds": 1,
        "llm_healthcheck_ttl_seconds": 300,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_llm_health_requires_configuration() -> None:
    gateway = LlmGateway(llm_settings(llm_api_key=""))
    assert await gateway.health_status() == "unconfigured"


@pytest.mark.asyncio
async def test_llm_health_success_is_cached() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    gateway = LlmGateway(llm_settings(), httpx.MockTransport(handler))
    assert await gateway.health_status() == "ok"
    assert await gateway.health_status() == "ok"
    assert calls == 1


@pytest.mark.asyncio
async def test_llm_health_reports_authentication_failure() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(401, json={"error": "invalid key"}))
    gateway = LlmGateway(llm_settings(), transport)
    assert await gateway.health_status() == "auth_error"


@pytest.mark.asyncio
async def test_llm_health_reports_unreachable_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("provider unavailable", request=request)

    gateway = LlmGateway(llm_settings(), httpx.MockTransport(handler))
    assert await gateway.health_status() == "unreachable"
