"""Build a minimal regular-file context, including from OneDrive on Windows."""

import argparse
import io
import subprocess
import tarfile
import tempfile
from pathlib import Path


def write_context(root: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for directory in ("backend/app", "analytics"):
            for path in sorted((root / directory).rglob("*")):
                relative = path.relative_to(root)
                if not path.is_file() or any(
                    part
                    in {".validation", "__pycache__", ".dbt-runtime", "dbt_packages"}
                    or part.startswith(".venv")
                    for part in relative.parts
                ):
                    continue
                if relative.parts[0] == "analytics" and any(
                    part in {"target", "logs"} for part in relative.parts
                ):
                    continue
                if path.suffix in {".pyc", ".log"} or path.name.startswith(".env"):
                    continue
                data = path.read_bytes()
                item = tarfile.TarInfo(relative.as_posix())
                item.size, item.mode = len(data), 0o644
                archive.addfile(item, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="ragmatch-market-worker:local")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="ragmatch-market-build-") as folder:
        context = Path(folder) / "context.tar"
        write_context(root, context)
        with context.open("rb") as stream:
            subprocess.run(
                [
                    "docker",
                    "build",
                    "--file",
                    "analytics/Dockerfile",
                    "--tag",
                    args.tag,
                    "-",
                ],
                stdin=stream,
                check=True,
            )


if __name__ == "__main__":
    main()
