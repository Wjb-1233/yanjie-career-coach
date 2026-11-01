"""question bank items become objects

Revision ID: 20261029_0012
Revises: 20261029_0011
Create Date: 2026-10-29
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0012"
down_revision: Union[str, None] = "20261029_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, question_bank FROM scenes")).fetchall()
    for scene_id, raw in rows:
        if raw is None:
            continue
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except Exception:
                continue
        else:
            data = raw
        if not isinstance(data, list) or not data:
            continue
        converted = []
        for item in data:
            if isinstance(item, str):
                if item.strip():
                    converted.append({"text": item.strip(), "dimension": None, "difficulty": None})
            elif isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                if text:
                    converted.append(
                        {
                            "text": text,
                            "dimension": item.get("dimension"),
                            "difficulty": item.get("difficulty"),
                        }
                    )
        conn.execute(
            sa.text("UPDATE scenes SET question_bank = :value WHERE id = :id"),
            {"value": json.dumps(converted, ensure_ascii=False), "id": scene_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, question_bank FROM scenes")).fetchall()
    for scene_id, raw in rows:
        if raw is None:
            continue
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, list):
            continue
        texts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in data]
        conn.execute(
            sa.text("UPDATE scenes SET question_bank = :value WHERE id = :id"),
            {"value": json.dumps(texts, ensure_ascii=False), "id": scene_id},
        )
