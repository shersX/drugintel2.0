"""开发启动：数据库和 Redis 留在 Docker，前后端在本机热更新。

用法：python start.py
页面：http://127.0.0.1:5173
接口：http://127.0.0.1:8000
结束：Ctrl+C

开发结束后，仍用 docker compose up -d --build 把前后端放回容器。
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def _compose(*args: str) -> bool:
    if shutil.which("docker"):
        cmd = ["docker", "compose", *args]
        cwd = ROOT
    elif os.name == "nt" and shutil.which("wsl"):
        cmd = ["wsl", "--cd", str(ROOT), "docker", "compose", *args]
        cwd = None
    else:
        return False
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode == 0


def _prepare_docker() -> None:
    print("启动数据库和 Redis，并停掉容器里的 app（释放 8000 端口）")
    if not _compose("up", "-d", "db", "redis"):
        print("未能调用 docker compose。请先在项目目录执行：docker compose up -d db redis")
        return
    _compose("stop", "app")


def _ensure_schema() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from backend.src.db.schema import ensure_schema

    for attempt in range(1, 31):
        try:
            ensure_schema()
            return
        except Exception as exc:
            if attempt >= 30:
                raise SystemExit(f"数据库未就绪：{exc}") from exc
            print(f"等待数据库…（{attempt}/30）")
            time.sleep(2)


def _npm() -> str:
    if os.name == "nt":
        found = shutil.which("npm.cmd") or shutil.which("npm")
    else:
        found = shutil.which("npm")
    if not found:
        raise SystemExit("未找到 npm。请先安装 Node.js。")
    return found


def _ensure_frontend_deps() -> None:
    if (FRONTEND / "node_modules").exists():
        return
    print("安装前端依赖…")
    subprocess.run([_npm(), "install"], cwd=FRONTEND, check=True)


def _popen(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    kwargs: dict = {"cwd": cwd, "env": env}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _stop(procs: list[subprocess.Popen]) -> None:
    for proc in procs:
        if proc.poll() is not None:
            continue
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                proc.terminate()
    deadline = time.time() + 8
    for proc in procs:
        remaining = max(0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()


def _backend_cmd() -> list[str]:
    """优先 uv；没有则用当前解释器（conda / venv / 系统 Python）。"""
    uvicorn_args = [
        "uvicorn",
        "backend.src.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]
    if shutil.which("uv"):
        return ["uv", "run", *uvicorn_args]
    try:
        import uvicorn  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "未找到 uv，且当前 Python 未安装项目依赖。\n"
            "请任选其一：\n"
            "  1) 安装 uv 后执行：uv sync\n"
            "  2) 在 conda 环境中执行：pip install -e .\n"
            f"当前解释器：{sys.executable}"
        ) from exc
    print(f"未使用 uv，改用当前 Python：{sys.executable}")
    return [sys.executable, "-m", *uvicorn_args]


def main() -> None:
    os.chdir(ROOT)
    backend_cmd = _backend_cmd()
    _prepare_docker()
    _ensure_schema()
    _ensure_frontend_deps()

    env = os.environ.copy()
    if sys.platform != "win32" and "/mnt/" in str(ROOT):
        env["WATCHFILES_FORCE_POLLING"] = "true"

    backend = _popen(backend_cmd, ROOT, env)
    frontend = _popen(
        [_npm(), "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
        FRONTEND,
        env,
    )
    procs = [backend, frontend]
    print("前端  http://127.0.0.1:5173")
    print("接口  http://127.0.0.1:8000")
    print("按 Ctrl+C 停止前后端。数据库和 Redis 容器会继续运行。")
    try:
        while True:
            for proc in procs:
                code = proc.poll()
                if code is not None:
                    raise SystemExit(code)
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\n正在停止前后端…")
    finally:
        _stop(procs)


if __name__ == "__main__":
    main()
