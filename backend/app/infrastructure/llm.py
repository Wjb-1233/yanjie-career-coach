import asyncio
import json
import re
from collections.abc import AsyncIterator
from time import monotonic
from typing import Any

import httpx

from app.core.config import Settings, settings


class LlmGateway:
    def __init__(
        self,
        config: Settings = settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._health_lock = asyncio.Lock()
        self._health_status = "unconfigured" if not self.configured else "unknown"
        self._health_checked_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.config.llm_api_key)

    async def health_status(self, *, force: bool = False) -> str:
        if not self.configured:
            return "unconfigured"

        now = monotonic()
        if (
            not force
            and self._health_checked_at
            and now - self._health_checked_at < self.config.llm_healthcheck_ttl_seconds
        ):
            return self._health_status

        async with self._health_lock:
            now = monotonic()
            if (
                not force
                and self._health_checked_at
                and now - self._health_checked_at < self.config.llm_healthcheck_ttl_seconds
            ):
                return self._health_status

            status = "error"
            try:
                payload = {
                    "model": self.config.llm_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Reply with OK only. This is a service health check.",
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 1,
                    "stream": False,
                }
                timeout = httpx.Timeout(
                    self.config.llm_healthcheck_timeout_seconds,
                    connect=min(3.0, self.config.llm_healthcheck_timeout_seconds),
                )
                async with httpx.AsyncClient(
                    base_url=self.config.llm_base_url.rstrip("/"),
                    headers={"Authorization": f"Bearer {self.config.llm_api_key}"},
                    timeout=timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.post("/chat/completions", json=payload)
                    response.raise_for_status()
                choices = response.json().get("choices")
                status = "ok" if isinstance(choices, list) and choices else "invalid_response"
            except httpx.HTTPStatusError as exc:
                status = "auth_error" if exc.response.status_code in (401, 403) else "upstream_error"
            except httpx.RequestError:
                status = "unreachable"
            except (TypeError, ValueError, json.JSONDecodeError):
                status = "invalid_response"
            finally:
                self._health_status = status
                self._health_checked_at = monotonic()
            return status

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1600,
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("LLM_API_KEY is not configured")
        payload: dict[str, Any] = {
            "model": self.config.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if self.config.llm_json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(
            base_url=self.config.llm_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {self.config.llm_api_key}"},
            timeout=self.config.llm_timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return self._parse_json(content)

    async def stream_text(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 350,
    ) -> AsyncIterator[str]:
        if not self.configured:
            raise RuntimeError("LLM_API_KEY is not configured")
        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        timeout = httpx.Timeout(
            self.config.llm_timeout_seconds,
            connect=min(3.0, self.config.llm_timeout_seconds),
        )
        async with httpx.AsyncClient(
            base_url=self.config.llm_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {self.config.llm_api_key}"},
            timeout=timeout,
            transport=self._transport,
        ) as client:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    event = json.loads(raw)
                    choices = event.get("choices") or []
                    if choices:
                        text = (choices[0].get("delta") or {}).get("content")
                        if text:
                            yield text

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.S)
        if fenced:
            cleaned = fenced.group(1)
        if not cleaned.startswith("{"):
            match = re.search(r"\{.*\}", cleaned, re.S)
            if match:
                cleaned = match.group(0)
        return json.loads(cleaned)


llm_gateway = LlmGateway()

