"""进程内指标：Prometheus 文本格式，不引入额外依赖。

只记录路由模板而不是真实路径，避免用户 ID / 会话 ID 造成标签爆炸。
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

_lock = threading.Lock()
_started_at = time.time()

_requests: dict[tuple[str, str, str], int] = defaultdict(int)
_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_duration_count: dict[tuple[str, str], int] = defaultdict(int)
_buckets: dict[tuple[str, str, float], int] = defaultdict(int)
_errors: dict[str, int] = defaultdict(int)

# 业务侧计数（评分降级、任务失败等），由调用方显式增加
_events: dict[tuple[str, str], int] = defaultdict(int)


def observe_request(method: str, route: str, status: int, seconds: float) -> None:
    key = (method, route, str(status))
    dur_key = (method, route)
    with _lock:
        _requests[key] += 1
        _duration_sum[dur_key] += seconds
        _duration_count[dur_key] += 1
        for bucket in BUCKETS:
            if seconds <= bucket:
                _buckets[(method, route, bucket)] += 1
        if status >= 500:
            _errors[route] += 1


def incr_event(name: str, outcome: str = "ok", value: int = 1) -> None:
    with _lock:
        _events[(name, outcome)] += value


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render() -> str:
    from app.core.config import settings

    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except Exception:  # noqa: BLE001 - Windows 无 resource
        rss = 0

    lines: list[str] = []
    with _lock:
        requests = dict(_requests)
        duration_sum = dict(_duration_sum)
        duration_count = dict(_duration_count)
        buckets = dict(_buckets)
        errors = dict(_errors)
        events = dict(_events)

    lines.append("# HELP app_info 应用基本信息")
    lines.append("# TYPE app_info gauge")
    lines.append(
        f'app_info{{environment="{_escape(settings.environment)}",app="{_escape(settings.app_name)}"}} 1'
    )

    lines.append("# HELP process_uptime_seconds 进程已运行秒数")
    lines.append("# TYPE process_uptime_seconds gauge")
    lines.append(f"process_uptime_seconds {time.time() - _started_at:.1f}")

    if rss:
        lines.append("# HELP process_resident_memory_bytes 常驻内存")
        lines.append("# TYPE process_resident_memory_bytes gauge")
        lines.append(f"process_resident_memory_bytes {rss}")

    lines.append("# HELP http_requests_total 按方法/路由/状态码统计的请求数")
    lines.append("# TYPE http_requests_total counter")
    for (method, route, status), count in sorted(requests.items()):
        lines.append(
            f'http_requests_total{{method="{method}",route="{_escape(route)}",status="{status}"}} {count}'
        )

    lines.append("# HELP http_request_duration_seconds 请求耗时直方图")
    lines.append("# TYPE http_request_duration_seconds histogram")
    for method, route in sorted({(m, r) for (m, r, _s) in requests}):
        for bucket in BUCKETS:
            value = buckets.get((method, route, bucket), 0)
            lines.append(
                f'http_request_duration_seconds_bucket{{method="{method}",route="{_escape(route)}",le="{bucket}"}} {value}'
            )
        lines.append(
            f'http_request_duration_seconds_bucket{{method="{method}",route="{_escape(route)}",le="+Inf"}} '
            f"{duration_count.get((method, route), 0)}"
        )
        lines.append(
            f'http_request_duration_seconds_sum{{method="{method}",route="{_escape(route)}"}} '
            f"{duration_sum.get((method, route), 0.0):.6f}"
        )
        lines.append(
            f'http_request_duration_seconds_count{{method="{method}",route="{_escape(route)}"}} '
            f"{duration_count.get((method, route), 0)}"
        )

    lines.append("# HELP http_errors_total 5xx 次数")
    lines.append("# TYPE http_errors_total counter")
    for route, count in sorted(errors.items()):
        lines.append(f'http_errors_total{{route="{_escape(route)}"}} {count}')

    lines.append("# HELP app_events_total 业务事件（评分降级、任务失败等）")
    lines.append("# TYPE app_events_total counter")
    for (name, outcome), count in sorted(events.items()):
        lines.append(f'app_events_total{{event="{_escape(name)}",outcome="{_escape(outcome)}"}} {count}')

    return "\n".join(lines) + "\n"
