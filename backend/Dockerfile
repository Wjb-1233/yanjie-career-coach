# 生产镜像：单进程 uvicorn（后台任务 worker 与 Web 同进程，见部署指南）
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# mediapipe / whisper 运行需要的系统库；ffmpeg 供语音与分段使用
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p static/recordings static/lessons static/tts .models \
    && chown -R app:app /app

USER app

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8081/api/v1/health || exit 1

# 单 worker：分析任务 worker 跑在应用进程内；多 worker 时任务领取已用 SKIP LOCKED，
# 但模型常驻内存，按内存预算再决定是否扩容。
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8081", \
     "--workers", "1", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
