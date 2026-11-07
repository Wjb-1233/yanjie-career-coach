"""备份恢复演练：把生产库 dump 出来，恢复到一个临时库，校验数据后清理。

用法（生产机、容器名按 compose 项目名）：
    python3 scripts/restore_check.py --container career-coach-prod-mysql-1
    python3 scripts/restore_check.py --container career-coach-mysql-1 --keep

退出码 0 表示恢复成功且核心表行数一致，非 0 表示演练失败。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime

CORE_TABLES = ["users", "scenes", "training_sessions", "evaluations", "messages"]


def _exec(
    container: str,
    script: str,
    *,
    stdin: str | bytes | None = None,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """文本模式用于统计；dump/恢复用二进制模式，避免 Windows 本地编码把中文 dump 解坏。"""
    return subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-c", script],
        input=stdin,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        timeout=600,
    )


def counts(container: str, database: str | None = None) -> dict[str, int]:
    target = database or '"$MYSQL_DATABASE"'
    # 临时库用 root 读，业务账号没有跨库权限
    login = (
        '-uroot -p"$MYSQL_ROOT_PASSWORD"'
        if database
        else '-u"$MYSQL_USER" -p"$MYSQL_PASSWORD"'
    )
    union = " UNION ALL ".join(f"SELECT '{table}', COUNT(*) FROM {table}" for table in CORE_TABLES)
    result = _exec(container, f'mysql -N -B {login} {target} -e {union!r}')
    if result.returncode != 0:
        raise RuntimeError(f"统计行数失败：{result.stderr[:400]}")
    parsed: dict[str, int] = {}
    for line in result.stdout.strip().splitlines():
        name, value = line.split("\t")
        parsed[name] = int(value)
    return parsed


def admin(container: str, statement: str) -> None:
    # 建库/删库需要 root 权限
    result = _exec(
        container,
        f'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e {statement!r}',
    )
    if result.returncode != 0:
        raise RuntimeError(f"执行失败：{statement}\n{result.stderr[:400]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", default="career-coach-mysql-1")
    parser.add_argument("--keep", action="store_true", help="演练后保留临时库，便于排查")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    temp_db = f"career_coach_restore_check_{stamp}"
    started = time.time()

    print(f"[1/5] 读取源库行数（{args.container}）")
    source = counts(args.container)
    print("     ", source)

    print("[2/5] 导出源库")
    dump = _exec(
        args.container,
        'mysqldump --single-transaction --routines --triggers '
        '-u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"',
        text=False,
    )
    if dump.returncode != 0:
        raise RuntimeError(f"导出失败：{dump.stderr[:400]!r}")
    print(f"      dump {len(dump.stdout)} bytes")

    try:
        print(f"[3/5] 创建临时库 {temp_db}")
        admin(args.container, f"CREATE DATABASE `{temp_db}` CHARACTER SET utf8mb4")

        print("[4/5] 恢复 dump 到临时库")
        restore = _exec(
            args.container,
            f'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" {temp_db}',
            stdin=dump.stdout,
            text=False,
        )
        if restore.returncode != 0:
            raise RuntimeError(f"恢复失败：{restore.stderr[:400]!r}")

        print("[5/5] 校验恢复后的行数")
        restored = counts(args.container, temp_db)
        print("     ", restored)
        mismatched = {
            table: (source.get(table), restored.get(table))
            for table in CORE_TABLES
            if source.get(table) != restored.get(table)
        }
        if mismatched:
            raise RuntimeError(f"行数不一致：{mismatched}")
        if sum(restored.values()) == 0:
            raise RuntimeError("恢复后的库是空的，dump 可能失败")

        print("\n恢复演练通过 ✓")
        print(f"  核心表行数一致：{restored}")
        print(f"  耗时 {time.time() - started:.1f}s")
    finally:
        if not args.keep:
            print(f"\n清理临时库 {temp_db}")
            admin(args.container, f"DROP DATABASE IF EXISTS `{temp_db}`")
        else:
            print(f"\n保留临时库 {temp_db}（--keep）")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"\n恢复演练失败 ✗\n{exc}", file=sys.stderr)
        sys.exit(1)
