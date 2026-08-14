from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
NODE = os.environ.get("MLIB_NODE") or os.environ.get("npm_node_execpath") or shutil.which("node")
LOCAL_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
BACKEND_PYTHON = os.environ.get("MLIB_PYTHON") or (str(LOCAL_PYTHON) if LOCAL_PYTHON.exists() else sys.executable)


def child_environment() -> dict[str, str]:
    """Return an environment without Windows' duplicate Path/PATH entries."""
    environment: dict[str, str] = {}
    for key, value in os.environ.items():
        normalized = "PATH" if os.name == "nt" and key.lower() == "path" else key
        environment[normalized] = value
    return environment


def wait_for_url(url: str, process: subprocess.Popen[bytes]) -> None:
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError(f"Server exited before {url} became ready")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}")


def start_server(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    log: object,
) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {
        "cwd": cwd,
        "env": environment,
        "stdout": log,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)  # type: ignore[arg-type]


def stop_server(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def print_log(path: Path) -> None:
    if path.exists():
        print(f"\n--- {path.name} ---", file=sys.stderr)
        print(path.read_text(encoding="utf-8", errors="replace")[-8_000:], file=sys.stderr)


def main() -> int:
    if not NODE:
        print("Node.js was not found in PATH", file=sys.stderr)
        return 1

    environment = child_environment()
    processes: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="mlib-e2e-", ignore_cleanup_errors=True) as temporary:
        temporary_path = Path(temporary)
        backend_log = temporary_path / "backend.log"
        frontend_log = temporary_path / "frontend.log"
        try:
            with backend_log.open("wb") as backend_output, frontend_log.open("wb") as frontend_output:
                frontend_environment = dict(environment)
                frontend_environment["BACKEND_INTERNAL_URL"] = "http://127.0.0.1:8100"
                frontend_environment["MLIB_E2E"] = "1"
                shutil.rmtree(FRONTEND / ".next", ignore_errors=True)
                build = subprocess.run(
                    [NODE, str(FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"), "build"],
                    cwd=FRONTEND,
                    env=frontend_environment,
                    check=False,
                )
                if build.returncode:
                    return build.returncode

                backend = start_server(
                    [BACKEND_PYTHON, str(FRONTEND / "e2e" / "start-backend.py")],
                    cwd=ROOT,
                    environment=environment,
                    log=backend_output,
                )
                processes.append(backend)
                wait_for_url("http://127.0.0.1:8100/health", backend)

                frontend = start_server(
                    [
                        NODE,
                        str(FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"),
                        "start",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        "3100",
                    ],
                    cwd=FRONTEND,
                    environment=frontend_environment,
                    log=frontend_output,
                )
                processes.append(frontend)
                wait_for_url("http://127.0.0.1:3100/login", frontend)

                test_environment = dict(frontend_environment)
                test_environment["MLIB_E2E_EXTERNAL_SERVERS"] = "1"
                result = subprocess.run(
                    [
                        NODE,
                        str(FRONTEND / "node_modules" / "@playwright" / "test" / "cli.js"),
                        "test",
                        *(sys.argv[2:] if sys.argv[1:2] == ["--"] else sys.argv[1:]),
                    ],
                    cwd=FRONTEND,
                    env=test_environment,
                    check=False,
                )
                return result.returncode
        except Exception as error:
            print(f"E2E environment failed: {error}", file=sys.stderr)
            print_log(backend_log)
            print_log(frontend_log)
            return 1
        finally:
            for process in reversed(processes):
                stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
