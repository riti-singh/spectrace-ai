"""Run the FastAPI API and Vite dashboard together for local development."""

import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    package_manager = shutil.which("pnpm")
    if package_manager is None:
        raise SystemExit("pnpm is required; install Node.js and enable Corepack first")

    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--reload"],
            cwd=PROJECT_ROOT,
        ),
        subprocess.Popen(
            [package_manager, "--dir", "frontend", "dev"],
            cwd=PROJECT_ROOT,
        ),
    ]
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.2)
        exit_code = next(
            process.returncode for process in processes if process.returncode is not None
        )
        raise SystemExit(exit_code)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()


if __name__ == "__main__":
    main()
