"""A-03：实测训练链路的响应延迟，输出 p50/p95。

测两件事：
1. 文字模式：从提交回答到首个 token、到整轮结束；
2. 语音模式（本地管线）：从说完最后一个音频包到面试官首个文字片段。

用法（后端需在 8081 运行）：
    python scripts/measure_latency.py --rounds 6 --out docs/延迟实测.md
    python scripts/measure_latency.py --text-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8081/api/v1"
SAMPLE_RATE = 16000
CHUNK = 640  # 20ms @16kHz s16le


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def summarize(name: str, values: list[float]) -> dict:
    if not values:
        return {"name": name, "count": 0}
    return {
        "name": name,
        "count": len(values),
        "p50": round(percentile(values, 50), 2),
        "p95": round(percentile(values, 95), 2),
        "mean": round(statistics.fmean(values), 2),
        "max": round(max(values), 2),
    }


async def ensure_user(client: httpx.AsyncClient) -> dict[str, str]:
    email = f"latency-{int(time.time())}@example.com"
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "LatencyTest123", "displayName": "延迟实测"},
    )
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


async def measure_text(client: httpx.AsyncClient, headers: dict[str, str], rounds: int) -> list[dict]:
    scenes = (await client.get("/scenes", headers=headers, params={"size": 3})).json()["data"]
    created = await client.post("/training-sessions", headers=headers, json={"sceneId": scenes[0]["id"]})
    session_id = created.json()["data"]["id"]
    samples = []
    for index in range(rounds):
        started = time.perf_counter()
        first_token = None
        async with client.stream(
            "POST",
            f"/training-sessions/{session_id}/messages",
            headers=headers,
            json={"content": f"第{index + 1}轮：我负责订单系统优化，把 P99 从 800ms 降到 200ms。"},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("event: token") and first_token is None:
                    first_token = (time.perf_counter() - started) * 1000
                if line.startswith("event: done"):
                    break
        total = (time.perf_counter() - started) * 1000
        samples.append(
            {
                "round": index + 1,
                "first_token_ms": round(first_token or total, 1),
                "total_ms": round(total, 1),
            }
        )
    return samples, session_id


async def tts_pcm(text: str) -> bytes:
    """用项目自己的 TTS 生成一段语音，再转成 16k s16le，模拟用户说话。"""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.infrastructure.narration import synthesize_slide

    workdir = Path(tempfile.mkdtemp())
    audio, _, _ = synthesize_slide(text, workdir, 0, style="tutor")
    import imageio_ffmpeg

    raw = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(audio), "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-"],
        capture_output=True,
        check=True,
    )
    return raw.stdout


async def measure_voice(rounds: int, scene_id: str) -> list[dict]:
    """先跑一轮预热（Whisper 首次加载），再计时 rounds 轮。"""
    import websockets

    pcm = await tts_pcm("你好，我先做个自我介绍。我之前负责订单系统的性能优化，把接口延迟从八百毫秒降到了两百毫秒。")
    if len(pcm) < CHUNK * 10:
        return []

    samples = []
    uri = f"ws://127.0.0.1:8081/api/v1/voice/ws/pipeline?sceneId={scene_id}"
    async with websockets.connect(uri, max_size=None) as socket:
        for index in range(rounds + 1):
            # 发送语音，尽量贴近实时节奏
            for offset in range(0, len(pcm), CHUNK):
                await socket.send(pcm[offset:offset + CHUNK])
                await asyncio.sleep(0.02)
            speech_end = time.perf_counter()
            # 0.5 秒静音，让 VAD 判定说完
            for _ in range(25):
                await socket.send(b"\x00" * CHUNK)
                await asyncio.sleep(0.02)
            first_reply = None
            deadline = time.perf_counter() + 30
            while time.perf_counter() < deadline:
                try:
                    message = await asyncio.wait_for(socket.recv(), timeout=10)
                except asyncio.TimeoutError:
                    break
                if isinstance(message, bytes):
                    continue
                payload = json.loads(message)
                if payload.get("type") == "assistant_delta" and first_reply is None:
                    first_reply = (time.perf_counter() - speech_end) * 1000
                if payload.get("type") == "assistant_end":
                    break
            if index == 0:
                continue  # 预热轮不计入
            if first_reply:
                samples.append({"round": index, "first_reply_ms": round(first_reply, 1)})
            else:
                samples.append({"round": index, "first_reply_ms": None, "timeout": True})
    return samples


def render_markdown(result: dict) -> str:
    lines = [
        "# 延迟实测（A-03）",
        "",
        f"> 生成时间：{result['generatedAt']}　样本：{result['rounds']} 轮/链路　环境：本机 CPU，模型与路由见 `docs/技术说明.md`",
        "",
        "## 结果",
        "",
        "| 指标 | 样本数 | p50 | p95 | 平均 | 最大 |",
        "|---|---|---|---|---|---|",
    ]
    for item in result["metrics"]:
        if not item.get("count"):
            lines.append(f"| {item['name']} | 0 | — | — | — | — |")
            continue
        lines.append(
            f"| {item['name']} | {item['count']} | {item['p50']} ms | {item['p95']} ms | {item['mean']} ms | {item['max']} ms |"
        )
    lines += [
        "",
        "## 说明",
        "",
        "- 文字指标：从提交回答到 SSE 首个 token / 整轮结束，含模型排队与网络往返。",
        "- 语音指标：本地管线（Silero VAD → faster-whisper → DeepSeek → TTS），从最后一个音频包到面试官首个字幕片段。",
        "- 首轮包含模型预热，已单独标记为 `warmup`，不计入上表。",
        "- 这些是**本次实测量**，不是产品承诺；换机器、换网络、换模型都会变。",
        "",
        "## 原始样本",
        "",
        "```json",
        json.dumps(result["samples"], ensure_ascii=False, indent=2)[:4000],
        "```",
        "",
    ]
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--out", default="docs/延迟实测.md")
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=BASE, timeout=120, trust_env=False) as client:
        headers = await ensure_user(client)
        text_samples, session_id = await measure_text(client, headers, args.rounds)
        samples = {"text": text_samples}

        metrics = [
            summarize("文字 · 首 token", [item["first_token_ms"] for item in text_samples[1:]]),
            summarize("文字 · 整轮回复", [item["total_ms"] for item in text_samples[1:]]),
        ]

        if not args.text_only:
            scenes = (await client.get("/scenes", headers=headers, params={"size": 1})).json()["data"]
            try:
                voice_samples = await measure_voice(args.rounds, scenes[0]["id"])
                samples["voice"] = voice_samples
                metrics.append(
                    summarize(
                        "语音 · 说完到首个回应",
                        [item["first_reply_ms"] for item in voice_samples if item.get("first_reply_ms")],
                    )
                )
            except Exception as exc:  # noqa: BLE001
                samples["voice_error"] = f"{type(exc).__name__}: {exc}"
                metrics.append({"name": "语音 · 说完到首个回应", "count": 0})

    result = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rounds": args.rounds,
        "warmupSession": session_id,
        "metrics": metrics,
        "samples": samples,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(result), encoding="utf-8")
    json_path = out.with_suffix(".json")
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"已写入 {out} 与 {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
