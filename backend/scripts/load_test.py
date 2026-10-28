"""Concurrent training endpoint benchmark with a machine-readable release report.

This script deliberately treats a degraded/local fallback reply as a failed release
gate unless ``--allow-degraded`` is supplied. It never writes access tokens or
passwords to the report.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(slots=True)
class AttemptResult:
    virtual_user: int
    success: bool = False
    status_code: int | None = None
    http_version: str | None = None
    create_session_ms: float | None = None
    response_headers_ms: float | None = None
    first_event_ms: float | None = None
    first_token_ms: float | None = None
    total_response_ms: float | None = None
    degraded: bool = False
    error: str | None = None


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 2)
    interpolated = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(interpolated, 2)


def metric_summary(results: list[AttemptResult], field: str) -> dict[str, float | None]:
    values = [float(value) for item in results if (value := getattr(item, field)) is not None]
    return {
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "max": round(max(values), 2) if values else None,
    }


def build_summary(
    results: list[AttemptResult],
    *,
    wall_seconds: float,
    target_first_token_ms: float,
    allow_degraded: bool,
) -> dict[str, Any]:
    successes = [item for item in results if item.success]
    degraded_count = sum(item.degraded for item in successes)
    first_token = metric_summary(successes, "first_token_ms")
    gates = {
        "noRequestFailures": len(successes) == len(results),
        "noUnexpectedDegradation": allow_degraded or degraded_count == 0,
        "firstTokenP95WithinTarget": (
            first_token["p95"] is not None and first_token["p95"] <= target_first_token_ms
        ),
    }
    return {
        "virtualUsers": len(results),
        "successes": len(successes),
        "failures": len(results) - len(successes),
        "degradedResponses": degraded_count,
        "successRate": round(len(successes) / len(results), 4) if results else 0,
        "wallSeconds": round(wall_seconds, 3),
        "throughputResponsesPerSecond": round(len(successes) / wall_seconds, 3)
        if wall_seconds > 0
        else 0,
        "latencyMs": {
            "createSession": metric_summary(successes, "create_session_ms"),
            "responseHeaders": metric_summary(successes, "response_headers_ms"),
            "firstEvent": metric_summary(successes, "first_event_ms"),
            "firstToken": first_token,
            "totalResponse": metric_summary(successes, "total_response_ms"),
        },
        "releaseGates": gates,
        "passed": all(gates.values()),
    }


def parse_sse_data(line: str) -> dict[str, Any]:
    try:
        payload = json.loads(line.removeprefix("data:").strip())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def run_virtual_user(
    index: int,
    *,
    start: asyncio.Event,
    client: httpx.AsyncClient,
    token: str,
    scene_id: str,
    message: str,
) -> AttemptResult:
    result = AttemptResult(virtual_user=index)
    await start.wait()
    attempt_started = time.perf_counter()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        create_started = time.perf_counter()
        created = await client.post(
            "/training-sessions",
            headers=headers,
            json={"sceneId": scene_id},
        )
        result.create_session_ms = round((time.perf_counter() - create_started) * 1000, 2)
        result.status_code = created.status_code
        created.raise_for_status()
        session_id = created.json()["data"]["id"]

        stream_started = time.perf_counter()
        current_event = ""
        saw_done = False
        async with client.stream(
            "POST",
            f"/training-sessions/{session_id}/messages",
            headers=headers,
            json={"content": message},
        ) as response:
            result.status_code = response.status_code
            result.http_version = response.http_version
            result.response_headers_ms = round((time.perf_counter() - stream_started) * 1000, 2)
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    current_event = line.removeprefix("event:").strip()
                    continue
                if not line.startswith("data:"):
                    continue
                elapsed_ms = round((time.perf_counter() - stream_started) * 1000, 2)
                if result.first_event_ms is None:
                    result.first_event_ms = elapsed_ms
                if current_event == "token" and result.first_token_ms is None:
                    result.first_token_ms = elapsed_ms
                if current_event == "done":
                    payload = parse_sse_data(line)
                    result.degraded = bool(payload.get("degraded"))
                    saw_done = True

        result.total_response_ms = round((time.perf_counter() - stream_started) * 1000, 2)
        if result.first_token_ms is None:
            raise RuntimeError("SSE stream ended without a token event")
        if not saw_done:
            raise RuntimeError("SSE stream ended without a done event")
        result.success = True
    except Exception as exc:  # noqa: BLE001 - every virtual user must be represented in the report
        result.error = f"{type(exc).__name__}: {exc}"
        if result.total_response_ms is None:
            result.total_response_ms = round((time.perf_counter() - attempt_started) * 1000, 2)
    return result


async def resolve_tokens(client: httpx.AsyncClient, args: argparse.Namespace) -> list[str]:
    if args.tokens_file:
        tokens = [
            line.strip()
            for line in Path(args.tokens_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not tokens:
            raise RuntimeError("令牌文件为空")
        return tokens

    env_token = os.getenv("LOAD_TEST_TOKEN", "").strip()
    if env_token:
        return [env_token]

    email = args.email or os.getenv("LOAD_TEST_EMAIL", "").strip()
    password = os.getenv("LOAD_TEST_PASSWORD", "")
    if not email:
        raise RuntimeError("请使用 --email/LOAD_TEST_EMAIL，或设置 LOAD_TEST_TOKEN")
    if not password:
        if not sys.stdin.isatty():
            raise RuntimeError("非交互环境必须设置 LOAD_TEST_PASSWORD")
        password = getpass.getpass("压测账号密码（不会写入报告）：")

    response = await client.post("/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return [response.json()["data"]["accessToken"]]


def validate_target(args: argparse.Namespace) -> None:
    parsed = urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("--base-url 必须是完整的 HTTP(S) API 地址")
    if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTS and not args.allow_insecure_http:
        raise RuntimeError("远程压测地址必须使用 HTTPS；确需 HTTP 时显式添加 --allow-insecure-http")
    if args.users < 1 or args.users > 200:
        raise RuntimeError("--users 必须在 1 到 200 之间")


def write_report(path: str, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def benchmark(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    validate_target(args)
    timeout = httpx.Timeout(args.timeout, connect=min(5.0, args.timeout))
    limits = httpx.Limits(
        max_connections=max(args.users + 5, 20),
        max_keepalive_connections=max(args.users, 20),
    )
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=timeout,
        limits=limits,
        verify=not args.insecure_tls,
        follow_redirects=False,
        headers={"User-Agent": "career-coach-release-load-test/1.0"},
    ) as client:
        ready = await client.get("/ready")
        ready.raise_for_status()
        tokens = await resolve_tokens(client, args)
        scenes = await client.get(
            "/scenes",
            headers={"Authorization": f"Bearer {tokens[0]}"},
        )
        scenes.raise_for_status()
        available_scenes = scenes.json()["data"]
        if not available_scenes:
            raise RuntimeError("没有可用于压测的场景")
        scene_id = args.scene_id or available_scenes[0]["id"]

        start = asyncio.Event()
        tasks = [
            asyncio.create_task(
                run_virtual_user(
                    index,
                    start=start,
                    client=client,
                    token=tokens[(index - 1) % len(tokens)],
                    scene_id=scene_id,
                    message=args.message,
                )
            )
            for index in range(1, args.users + 1)
        ]
        await asyncio.sleep(0)
        wall_started = time.perf_counter()
        start.set()
        results = await asyncio.gather(*tasks)
        wall_seconds = time.perf_counter() - wall_started

    summary = build_summary(
        results,
        wall_seconds=wall_seconds,
        target_first_token_ms=args.target_first_token_ms,
        allow_degraded=args.allow_degraded,
    )
    report = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "target": {
            "baseUrl": args.base_url,
            "sceneId": scene_id,
            "virtualUsers": args.users,
            "identityCount": len(tokens),
            "identityMode": "distinct_tokens" if len(tokens) > 1 else "shared_token",
            "firstTokenTargetMs": args.target_first_token_ms,
            "allowDegraded": args.allow_degraded,
            "tlsVerification": not args.insecure_tls,
        },
        "readiness": ready.json().get("data", {}),
        "summary": summary,
        "attempts": [asdict(item) for item in results],
    }
    return report, 0 if summary["passed"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="职场沟通训练接口并发与首 token 性能验收")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/api/v1")
    parser.add_argument("--users", type=int, default=20, help="并发虚拟用户数，默认 20")
    parser.add_argument("--email", help="登录邮箱；密码从 LOAD_TEST_PASSWORD 读取或安全提示输入")
    parser.add_argument("--tokens-file", help="每行一个短期 access token，可用于真实多身份压测")
    parser.add_argument("--scene-id", help="指定场景 ID；默认使用第一个场景")
    parser.add_argument(
        "--message",
        default="我会先说明当前进展和风险，再提出需要团队共同确认的下一步安排。",
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="每个请求超时秒数")
    parser.add_argument("--target-first-token-ms", type=float, default=3000.0)
    parser.add_argument("--output", default="reports/load-test.json")
    parser.add_argument("--allow-degraded", action="store_true", help="仅本地兜底模式使用")
    parser.add_argument("--allow-insecure-http", action="store_true")
    parser.add_argument("--insecure-tls", action="store_true", help="仅临时预发布证书使用")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report, exit_code = asyncio.run(benchmark(args))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"压测未执行：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    write_report(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"报告已写入：{Path(args.output).resolve()}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
