from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DEFAULT_ARCHIVE = ROOT / "dist" / f"findcare-search-portable-v{VERSION}.zip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a clean FindCare portable distribution.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--port", type=int, default=18355)
    parser.add_argument("--timeout", type=int, default=420)
    return parser.parse_args()


def wait_json(url: str, process: subprocess.Popen, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Launcher exited before readiness with code {process.returncode}")
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310 - loopback verification only
                return json.loads(response.read())
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    raise TimeoutError(f"Timed out waiting for {url}")


def wait_http(url: str, process: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Process exited before {url} became available")
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310 - loopback verification only
                response.read(1)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for {url}")


def wait_port_closed(port: int, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as client:
            if client.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.2)
    raise TimeoutError(f"Port {port} did not close")


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def log_tail(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def wait_log_contains(path: Path, needle: str, process: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Launcher exited before reporting {needle!r}")
        if path.exists() and needle in path.read_text(encoding="utf-8", errors="replace"):
            return
        time.sleep(0.2)
    raise TimeoutError(f"Launcher did not report {needle!r}")


def launch(package_dir: Path, port: int, log_path: Path, env: dict[str, str]) -> tuple[subprocess.Popen, object]:
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(package_dir / "run.sh")],
        cwd=package_dir,
        env={**env, "PORT": str(port), "NO_BROWSER": "1"},
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, log_file


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve()
    if not archive.is_file():
        raise SystemExit(f"Archive not found: {archive}")

    clean_env = os.environ.copy()
    for key in ("ATLAS_URI", "VOYAGE_API_KEY", "ATLAS_DB", "ATLAS_COLLECTION"):
        clean_env.pop(key, None)

    with tempfile.TemporaryDirectory(prefix="findcare-portable-verify-") as directory:
        extract_root = Path(directory)
        subprocess.run(
            ["unzip", "-q", str(archive), "-d", str(extract_root)],
            check=True,
        )
        package_dirs = [path for path in extract_root.iterdir() if path.is_dir()]
        if len(package_dirs) != 1:
            raise RuntimeError("Expected one package directory after extraction")
        package_dir = package_dirs[0]
        if (package_dir / ".env").exists():
            raise RuntimeError("Portable package is not secret-free")
        providers = json.loads(
            (package_dir / "data" / "findcare_providers.json").read_text(encoding="utf-8")
        )
        if len(providers) != 100 or any("embedding" in provider for provider in providers):
            raise RuntimeError("Bundled provider fixture is missing, incomplete, or contains embeddings")

        print("[1/5] Clean extraction is secret-free and contains 100 synthetic providers")
        first_log = extract_root / "first-run.log"
        first, first_handle = launch(package_dir, args.port, first_log, clean_env)
        try:
            ready = wait_json(f"http://127.0.0.1:{args.port}/ready", first, args.timeout)
            wait_log_contains(first_log, "FindCare is ready:", first, 20)
            if ready != {"status": "ready", "configured": False}:
                raise RuntimeError(f"Unexpected initial readiness response: {ready}")
            with urlopen(f"http://127.0.0.1:{args.port}/api/setup", timeout=3) as response:  # noqa: S310
                setup = json.loads(response.read())
            if setup.get("configured") or "atlas_uri" in setup or "voyage_api_key" in setup:
                raise RuntimeError(f"Setup endpoint exposed an invalid initial state: {setup}")
            with urlopen(f"http://127.0.0.1:{args.port}/", timeout=3) as response:  # noqa: S310
                page = response.read()
                if b"FindCare" not in page or b"Search Studio" not in page:
                    raise RuntimeError("FindCare UI did not load")
            if not (package_dir / "vendor" / "python" / "install" / "bin" / "python3").is_file():
                raise RuntimeError("Pinned standalone Python was not installed")
            venv_python = package_dir / ".venv" / "bin" / "python"
            subprocess.run(
                [str(venv_python), "-c", "import fastapi, pymongo, uvicorn, voyageai"],
                check=True,
                cwd=package_dir,
            )
            print("[2/5] First-run runtime and pinned dependencies installed")
            print("[3/5] UI, API readiness, and secret-free setup state verified")

            warm_log = extract_root / "warm-restart.log"
            started = time.monotonic()
            warm, warm_handle = launch(package_dir, args.port, warm_log, clean_env)
            try:
                try:
                    first.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"Warm launcher log:\n{log_tail(warm_log)}")
                ready = wait_json(f"http://127.0.0.1:{args.port}/ready", warm, 45)
                wait_log_contains(warm_log, "FindCare is ready:", warm, 20)
                elapsed = time.monotonic() - started
                if ready.get("status") != "ready" or elapsed > 45:
                    raise RuntimeError(f"Warm restart was not ready in time: {elapsed:.1f}s")
                print(f"[4/5] Warm restart safely handed off the port in {elapsed:.1f}s")
            finally:
                stop(warm)
                warm_handle.close()
            wait_port_closed(args.port)
        except Exception:
            print(log_tail(first_log))
            raise
        finally:
            stop(first)
            first_handle.close()
        wait_port_closed(args.port)

        unrelated_log = extract_root / "unrelated.log"
        with unrelated_log.open("w", encoding="utf-8") as unrelated_handle:
            unrelated = subprocess.Popen(
                [str(package_dir / ".venv" / "bin" / "python"), "-m", "http.server", str(args.port), "--bind", "127.0.0.1"],
                cwd=package_dir,
                stdout=unrelated_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                wait_http(f"http://127.0.0.1:{args.port}/", unrelated, 15)
                blocked = subprocess.run(
                    [str(package_dir / "run.sh")],
                    cwd=package_dir,
                    env={**clean_env, "PORT": str(args.port), "NO_BROWSER": "1"},
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                if blocked.returncode == 0 or unrelated.poll() is not None:
                    raise RuntimeError("Launcher did not preserve the unrelated listener")
                if "belongs to another application" not in f"{blocked.stdout}\n{blocked.stderr}":
                    raise RuntimeError("Launcher refusal did not explain the port conflict")
                print("[5/5] Unrelated listener was detected and left running")
            finally:
                stop(unrelated)

        print("Portable distribution verification passed.")


if __name__ == "__main__":
    main()
