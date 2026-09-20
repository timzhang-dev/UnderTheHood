"""Computes each case's expected output by running the program on a real JVM.

  cd backend && uv run python -m evals.build_gold

This is the eval's ground truth, and the reason no model output is ever gold: the
JVM is an independent oracle. The result is committed as gold.json so the eval itself
needs no JDK, and so a reviewer can read exactly what the JVM said.

It also checks each case's declared `expect` against reality: an `ok` case must run
cleanly, an `exception` case must die with the named exception, a program declared
`compiles=False` must be refused by javac, and every other program we decline must
still be valid Java (so a decline is a scope decision, not a broken test).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from evals.cases import CASES, Case

GOLD_PATH = Path(__file__).resolve().parent / "gold.json"
_EXCEPTION = re.compile(r'Exception in thread "main" ([\w.$]+)')
_COMPILE_ERROR = re.compile(r"Main\.java:(\d+): error: (.+)")


class OracleError(Exception):
    pass


def jdk_version() -> str:
    out = subprocess.run(["java", "-version"], capture_output=True, text=True)
    return (out.stderr or out.stdout).splitlines()[0].strip()


def _compile(tmp: str, source: str) -> subprocess.CompletedProcess:
    path = Path(tmp) / "Main.java"
    path.write_text(source)
    return subprocess.run(["javac", "-d", tmp, str(path)], capture_output=True, text=True, timeout=60)


def compile_error(source: str) -> str | None:
    """The compiler's first complaint ('line 3: ...'), or None if the program compiles."""
    with tempfile.TemporaryDirectory() as tmp:
        result = _compile(tmp, source)
    if result.returncode == 0:
        return None
    found = _COMPILE_ERROR.search(result.stderr)
    return f"line {found.group(1)}: {found.group(2)}" if found else result.stderr.strip().splitlines()[0]


def run_java(source: str, timeout_s: float = 10.0) -> dict:
    """Compiles and runs `source` as Main.java. Returns stdout lines, exit code, exception name."""
    with tempfile.TemporaryDirectory() as tmp:
        compiled = _compile(tmp, source)
        if compiled.returncode != 0:
            raise OracleError(f"does not compile:\n{compiled.stderr}")
        try:
            ran = subprocess.run(["java", "-cp", tmp, "Main"], capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise OracleError(f"did not finish within {timeout_s}s") from exc

    lines = ran.stdout.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    found = _EXCEPTION.search(ran.stderr)
    return {
        "stdout": lines,
        "exit_code": ran.returncode,
        "exception": found.group(1).split(".")[-1] if found else None,
    }


def check_against_expectation(case: Case, result: dict) -> str | None:
    if case.expect == "exception":
        if result["exit_code"] == 0 or result["exception"] != case.exception:
            return f"expected {case.exception}, JVM said exit={result['exit_code']} exception={result['exception']}"
    elif result["exit_code"] != 0:
        return f"expected a clean run, JVM said exit={result['exit_code']} exception={result['exception']}"
    return None


def main() -> int:
    jdk = jdk_version()
    gold: dict[str, dict] = {}
    problems = []
    for case in CASES:
        if not case.oracle:
            print(f"  skip   {case.id}  (not run on the JVM)")
            continue

        if not case.compiles:
            error = compile_error(case.source)
            if error is None:
                problems.append(f"{case.id}: declared as not compiling, but javac accepted it")
                print(f"  FAIL   {case.id}")
                continue
            gold[case.id] = {"compiles": False, "compile_error": error, "jdk": jdk}
            print(f"  ok     {case.id:32} javac refused: {error}")
            continue

        try:
            result = run_java(case.source)
        except OracleError as exc:
            problems.append(f"{case.id}: {exc}")
            print(f"  FAIL   {case.id}")
            continue
        problem = check_against_expectation(case, result)
        if problem:
            problems.append(f"{case.id}: {problem}")
        gold[case.id] = {"compiles": True, **result, "jdk": jdk}
        print(f"  {'FAIL' if problem else 'ok  '}   {case.id:32} stdout={result['stdout']} exception={result['exception']}")

    if problems:
        print("\nProblems (gold.json not written):", *problems, sep="\n  - ")
        return 1
    GOLD_PATH.write_text(json.dumps(gold, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {GOLD_PATH.name}: {len(gold)} programs checked on {jdk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
