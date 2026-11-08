"""本地判题：在临时目录里用子进程运行 Python / JavaScript 解法。

注意：这是练习用本地沙箱，只做了超时、输出上限和环境隔离，
没有容器级隔离；不要在公网环境直接暴露给不可信用户。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 6
MAX_OUTPUT = 20000
MARK = "__YANJIE_RESULT__"


def _python_harness(entry: str) -> str:
    return f'''
import json, sys
sys.path.insert(0, ".")
from solution import {entry} as target  # noqa

cases = json.loads(sys.stdin.read())
results = []
for args in cases:
    try:
        value = target(*args)
        results.append({{"ok": True, "value": value}})
    except Exception as exc:  # noqa: BLE001
        results.append({{"ok": False, "error": type(exc).__name__ + ": " + str(exc)}})
print("{MARK}" + json.dumps(results, ensure_ascii=False))
'''


def _js_harness(entry: str) -> str:
    return f'''
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("solution.js", "utf8");
const context = {{ module: {{ exports: {{}} }}, exports: {{}} }};
vm.createContext(context);
vm.runInContext(code + "\\n; globalThis.__entry = typeof {entry} === 'function' ? {entry} : undefined;", context);
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
const results = cases.map((args) => {{
  try {{
    if (typeof context.__entry !== "function") throw new Error("没有找到函数 {entry}");
    return {{ ok: true, value: context.__entry(...args) }};
  }} catch (error) {{
    return {{ ok: false, error: String(error && error.message ? error.message : error) }};
  }}
}});
process.stdout.write("{MARK}" + JSON.stringify(results));
'''


def _equals(actual, expected) -> bool:
    if isinstance(actual, float) and isinstance(expected, int | float):
        return abs(actual - expected) < 1e-6
    return actual == expected


def run_cases(language: str, code: str, entry: str, cases: list[dict]) -> list[dict]:
    workdir = Path(tempfile.mkdtemp(prefix="yanjie-code-"))
    try:
        if language == "python":
            (workdir / "solution.py").write_text(code, encoding="utf-8")
            (workdir / "harness.py").write_text(_python_harness(entry), encoding="utf-8")
            command = [sys.executable, "-I", "harness.py"]
        elif language == "javascript":
            (workdir / "solution.js").write_text(code, encoding="utf-8")
            (workdir / "harness.js").write_text(_js_harness(entry), encoding="utf-8")
            node = shutil.which("node")
            if not node:
                raise RuntimeError("当前环境没有安装 Node，无法运行 JavaScript")
            command = [node, "harness.js"]
        else:
            raise RuntimeError("暂不支持这门语言")

        payload = json.dumps([case["args"] for case in cases], ensure_ascii=False)
        try:
            completed = subprocess.run(
                command,
                input=payload,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=workdir,
                env=({**os.environ, "PATH": os.environ.get("PATH", "")} if language == "javascript" else None),
            )
        except subprocess.TimeoutExpired:
            return [
                {
                    "index": index + 1,
                    "input": case["args"],
                    "expected": case["expected"],
                    "actual": None,
                    "passed": False,
                    "error": f"运行超时（>{TIMEOUT_SECONDS}s）",
                }
                for index, case in enumerate(cases)
            ]

        stdout = (completed.stdout or "")[:_MAX_OUTPUT]
        stderr = (completed.stderr or "")[:_MAX_OUTPUT]
        results: list[dict] = []
        if MARK in stdout:
            raw = stdout.split(MARK, 1)[1].strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = []
        else:
            parsed = []
            stderr = stderr or "程序没有输出结果"

        if not parsed:
            return [
                {
                    "index": index + 1,
                    "input": case["args"],
                    "expected": case["expected"],
                    "actual": None,
                    "passed": False,
                    "error": stderr.strip()[:300] or "没有输出结果",
                }
                for index, case in enumerate(cases)
            ]

        for index, (case, item) in enumerate(zip(cases, parsed), start=1):
            passed = bool(item.get("ok")) and _equals(item.get("value"), case["expected"])
            results.append(
                {
                    "index": index,
                    "input": case["args"],
                    "expected": case["expected"],
                    "actual": item.get("value"),
                    "passed": passed,
                    "error": None if passed else (item.get("error") or "结果与预期不一致"),
                }
            )
        return results
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


_MAX_OUTPUT = MAX_OUTPUT
