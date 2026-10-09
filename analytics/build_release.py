"""Package the tested working tree without OneDrive links or local runtime data."""

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

API_BASE = "alvarocareli/ragmatch-api:sha-97a06d2e21c0ae69ecc971a7f42d7f76147a703a"
WEB_BASE = "alvarocareli/ragmatch-frontend:sha-97a06d2e21c0ae69ecc971a7f42d7f76147a703a"
WORKER_BASE = "ragmatch-market-validation:20261009-compatible"
SKIP = {".git", ".validation", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache", ".dbt-runtime", "dbt_packages", "target"}


def files(root, directory):
    directory = root / directory
    candidates = [directory] if directory.is_file() else sorted(directory.rglob("*"))
    for path in candidates:
        relative = path.relative_to(root)
        if not path.is_file() or any(part in SKIP or part.startswith(".venv") for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".log", ".dump", ".sqlite", ".db", ".pem", ".key"} or path.name.startswith(".env"):
            continue
        if relative.parts[0] == "analytics" and "logs" in relative.parts:
            continue
        yield relative.as_posix(), path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--namespace", default="alvarocareli")
    parser.add_argument("--worker-base", default=WORKER_BASE)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,100}", args.tag) or args.tag == "latest":
        parser.error("Use an explicit version tag, not latest.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.namespace):
        parser.error("Invalid Docker Hub namespace.")
    root = Path(__file__).resolve().parents[1]
    if not (root / "bid-buddy/dist-embed/index.html").is_file():
        parser.error("Build the CRM with npm run build:embed first.")
    components = {
        "api": (API_BASE, ["backend/app", "backend/scripts", "backend/alembic", "backend/alembic.ini"], 'COPY backend/app /app/app\nCOPY backend/scripts /app/scripts\nCOPY backend/alembic /app/alembic\nCOPY backend/alembic.ini /app/alembic.ini\nCMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]'),
        "frontend": (WEB_BASE, ["bid-buddy/dist-embed"], "COPY bid-buddy/dist-embed /usr/share/nginx/html/crm"),
        "market-worker": (args.worker_base, ["backend/app", "analytics"], "COPY --chown=10001:10001 backend/app /workspace/backend/app\nCOPY --chown=10001:10001 analytics /workspace/analytics"),
    }
    manifest = {"tag": args.tag, "images": {}, "source": "tested working tree; includes uncommitted implementation"}
    with tempfile.TemporaryDirectory(prefix="ragmatch-release-") as directory:
        for component, (base, paths, instructions) in components.items():
            entries = [entry for directory_path in paths for entry in files(root, directory_path)]
            digest = hashlib.sha256()
            for name, data in entries:
                digest.update(name.encode() + b"\0" + data + b"\0")
            source_hash = digest.hexdigest()
            image = f"{args.namespace}/ragmatch-{component}:{args.tag}"
            dockerfile = f'FROM {base}\nLABEL org.opencontainers.image.version="{args.tag}" io.ragmatch.source-sha256="{source_hash}"\n{instructions}\n'
            archive_path = Path(directory) / f"{component}.tar"
            with tarfile.open(archive_path, "w") as archive:
                for name, data in [("Dockerfile", dockerfile.encode()), *entries]:
                    item = tarfile.TarInfo(name)
                    item.size, item.mode = len(data), 0o644
                    archive.addfile(item, io.BytesIO(data))
            print(f"Building {image} from {len(entries)} files", flush=True)
            with archive_path.open("rb") as stream:
                subprocess.run(["docker", "build", "--tag", image, "-"], stdin=stream, check=True)
            manifest["images"][component] = {"image": image, "base": base, "source_sha256": source_hash}
    destination = root / "analytics/.validation/releases" / args.tag
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Built release. Validate these images before docker push; manifest: {destination / 'manifest.json'}")


if __name__ == "__main__":
    main()
