"""Build regular-file Docker contexts, including from OneDrive placeholders."""

import argparse
import subprocess
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["api", "frontend", "qa", "crm"])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--base", default="ragmatch-api:qa")
    parser.add_argument("--target")
    parser.add_argument("--crm-assets", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    files = []
    source = root / {"api": "backend", "frontend": "frontend", "crm": "bid-buddy"}.get(args.kind, "")
    if args.kind == "qa":
        for directory in ("backend/app", "backend/scripts", "backend/alembic", "qa", "analytics"):
            files.extend((root / directory).rglob("*"))
        files.append(root / "backend/alembic.ini")
        dockerfile = "qa/Dockerfile"
    else:
        files = list(source.rglob("*"))
        dockerfile = "Dockerfile"
        if args.kind == "crm":
            files.append(root / "qa/Dockerfile.crm")
    with tempfile.TemporaryDirectory(dir=root / ".validation") as folder:
        archive_path = Path(folder) / "context.tar"
        with tarfile.open(archive_path, "w") as archive:
            for path in files:
                relative = Path("Dockerfile") if path == root / "qa/Dockerfile.crm" else path.relative_to(root if args.kind == "qa" else source)
                if args.crm_assets and relative.as_posix().startswith("public/crm/"):
                    continue
                if not path.is_file() or any(part in {"__pycache__", "node_modules", "dist", "coverage", ".pytest_cache", ".validation"} or part.startswith(".env") for part in relative.parts):
                    continue
                if path.suffix in {".pyc", ".log"}:
                    continue
                data = path.read_bytes()
                entry = tarfile.TarInfo(relative.as_posix())
                entry.size, entry.mode = len(data), 0o644
                archive.addfile(entry, BytesIO(data))
            if args.crm_assets:
                for path in args.crm_assets.rglob("*"):
                    if path.is_file():
                        data = path.read_bytes()
                        entry = tarfile.TarInfo("public/crm/" + path.relative_to(args.crm_assets).as_posix())
                        entry.size, entry.mode = len(data), 0o644
                        archive.addfile(entry, BytesIO(data))
        command = ["docker", "build", "-f", dockerfile, "-t", args.tag]
        if args.kind == "qa":
            command += ["--build-arg", f"API_IMAGE={args.base}"]
        if args.target:
            command += ["--target", args.target]
        with archive_path.open("rb") as context:
            subprocess.run(command + ["-"], stdin=context, check=True)


if __name__ == "__main__":
    main()
