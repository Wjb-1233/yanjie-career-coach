import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TABLES = {
    "users",
    "refresh_tokens",
    "scenes",
    "favorites",
    "scripts",
    "training_sessions",
    "resume_contexts",
    "messages",
    "evaluations",
    "evaluation_evidence",
    "courses",
    "course_progress",
    "training_plans",
}


def table_names(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }


def test_initial_migration_upgrade_matches_models_and_downgrades(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+aiosqlite:///{database.as_posix()}",
    )

    command.upgrade(config, "head")
    assert BUSINESS_TABLES <= table_names(database)
    command.check(config)

    command.downgrade(config, "base")
    assert BUSINESS_TABLES.isdisjoint(table_names(database))


def test_degraded_migration_marks_existing_fallback_reports(tmp_path: Path) -> None:
    database = tmp_path / "old-report.db"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database.as_posix()}")
    command.upgrade(config, "20261009_0001")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO evaluations (
                id, session_id, user_id, logic_score, appropriateness_score,
                impact_score, relevance_score, concision_score, overall_score,
                summary, suggestions, style_tags, created_at
            ) VALUES (?, ?, ?, 3, 4, 3, 4, 4, 72, ?, '[]', '[]', ?)""",
            (
                "report-1",
                "session-1",
                "user-1",
                "表达基本完成了沟通目标。下一步应让结论更靠前，并用可验证事实支撑关键判断。",
                "2026-10-15 00:00:00",
            ),
        )
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        degraded = connection.execute("SELECT degraded FROM evaluations WHERE id = 'report-1'").fetchone()
    assert degraded == (1,)
