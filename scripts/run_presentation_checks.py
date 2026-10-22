"""Record focused verification results for the compact system guide."""

import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "dashboard/frontend"
OUTPUT = ROOT / "report/tinyfish_memory/ui-tests.json"


def main():
    results = []
    definitions = [
        (
            "Memory and presentation tests",
            [
                str(ROOT / ".venv/Scripts/python.exe"),
                "-m",
                "pytest",
                "tests/test_external_memory.py",
                "tests/test_agent_presentation.py",
                "-q",
                "--tb=short",
                "--show-capture=no",
            ],
            ROOT,
            "Isolated SQL / gateway contracts; real FalkorDB round trip excluded",
            "pytest",
        ),
        (
            "Dashboard unit tests",
            [shutil.which("npm.cmd"), "test"],
            FRONTEND,
            "JavaScript unit checks",
            "node",
        ),
        (
            "Dashboard production build",
            [shutil.which("npm.cmd"), "run", "build"],
            FRONTEND,
            "Production bundle",
            "build",
        ),
        (
            "Travel site production build",
            [shutil.which("npm.cmd"), "run", "build"],
            ROOT / "stitch_ai_travel_booking_platform/frontend",
            "Production bundle",
            "build",
        ),
        (
            "Dashboard and guide browser checks",
            [
                shutil.which("npx.cmd"),
                "playwright",
                "test",
                "tests/tinyfish-memory.spec.js",
                "--reporter=json",
            ],
            FRONTEND,
            "Labelled dashboard fixtures + actual generated HTML; desktop/mobile",
            "browser",
        ),
    ]
    for label, command, cwd, scope, kind in definitions:
        start = time.perf_counter()
        try:
            run = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf8",
                errors="replace",
                timeout=120,
            )
            passed, total = int(run.returncode == 0), 1
            if kind == "pytest":
                matches = re.findall(r"(\d+) passed", run.stdout)
                failures = re.findall(r"(\d+) failed|(?:^|\s)(\d+) errors?", run.stdout)
                passed = int(matches[-1]) if matches else 0
                total = passed + sum(int(a or b) for a, b in failures)
            elif kind == "node":
                passed = int(re.search(r"# pass (\d+)", run.stdout)[1])
                total = int(re.search(r"# tests (\d+)", run.stdout)[1])
            elif kind == "browser":
                stats = json.loads(run.stdout)["stats"]
                passed = stats["expected"]
                total = sum(
                    stats.get(key, 0)
                    for key in ["expected", "unexpected", "flaky", "skipped"]
                )
            result = dict(
                label=label,
                passed=passed,
                total=total,
                status="passed" if run.returncode == 0 else "failed",
                scope=scope,
                elapsed_seconds=round(time.perf_counter() - start, 2),
            )
            if run.returncode:
                result["error"] = (
                    "Check failed; rerun the recorded command for diagnostics."
                )
            result["command"] = subprocess.list2cmdline(command)
        except Exception as error:
            result = dict(
                label=label,
                passed=0,
                total=1,
                status="failed",
                scope=scope,
                error=type(error).__name__,
                elapsed_seconds=round(time.perf_counter() - start, 2),
            )
        results.append(result)
        report = dict(
            generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            checks=results,
            status="running"
            if len(results) < len(definitions)
            else "passed"
            if all(r["status"] == "passed" for r in results)
            else "partial",
        )
        OUTPUT.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf8", newline="\n"
        )
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
