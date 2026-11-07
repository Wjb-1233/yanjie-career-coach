#!/usr/bin/env bash
# 生产备份：数据库 + 录像/微课等媒体文件
# 用法（在仓库根目录、生产机上执行）：
#   ./scripts/backup.sh /backup/yanjie
# 依赖：docker compose（数据库在容器里）、tar
set -euo pipefail

TARGET="${1:-/backup/yanjie}"
STAMP="$(date +%Y%m%d-%H%M%S)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker-compose.prod.yml"

mkdir -p "$TARGET"

echo "[1/3] 导出数据库"
docker compose -f "$COMPOSE_FILE" exec -T mysql \
  sh -c 'exec mysqldump --single-transaction --routines --triggers -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  | gzip > "$TARGET/db-$STAMP.sql.gz"

echo "[2/3] 打包媒体文件（录像/微课/TTS）"
docker run --rm \
  -v career-coach-prod_recordings:/data/recordings:ro \
  -v career-coach-prod_lessons:/data/lessons:ro \
  -v career-coach-prod_tts:/data/tts:ro \
  -v "$TARGET":/backup \
  alpine:3.20 tar czf "/backup/media-$STAMP.tar.gz" -C /data .

echo "[3/3] 清理 14 天前的备份"
find "$TARGET" -name '*.gz' -mtime +14 -delete || true

echo "完成：$TARGET/db-$STAMP.sql.gz  $TARGET/media-$STAMP.tar.gz"
