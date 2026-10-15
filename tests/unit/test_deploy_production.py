"""Execute the deploy shell against fake Git/Docker, without touching a VPS."""

import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
TAG = f"sha-{SHA}-123-1"
SCRIPT = (ROOT / "scripts/deploy-production.sh").read_text(encoding="utf-8")


@pytest.fixture
def deploy(tmp_path):
    bash = (
        "C:/Program Files/Git/bin/bash.exe"
        if os.name == "nt"
        else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash is required for deployment contract tests")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env_file = tmp_path / ".env.prod"
    env_file.write_text("IMAGE_TAG=old-release\nDEPLOY_ANALYTICS=0\n", encoding="utf-8")
    archive = tmp_path / "compose.tar"
    with tarfile.open(archive, "w") as tar:
        for filename in (
            "docker-compose.prod.yaml",
            "docker-compose.analytics.yaml",
            "docker-compose.analytics.prod.yaml",
        ):
            contents = b"services: {}\n"
            info = tarfile.TarInfo(filename)
            info.size = len(contents)
            tar.addfile(info, io.BytesIO(contents))
    commands = {
        "git": '''
printf 'git %s\\n' "$*" >> "$MOCK_LOG"
if [[ "$1" == archive ]]; then cat "$MOCK_ARCHIVE"; fi
if [[ "$1" == merge-base && "${MOCK_NON_MAIN:-0}" == 1 ]]; then exit 1; fi
''',
        "docker": '''
printf 'docker %s tag=%s market=%s\\n' "$*" "$IMAGE_TAG" "${MARKET_WORKER_IMAGE:-}" >> "$MOCK_LOG"
if [[ "$*" == *' pull '* && "${MOCK_PULL_FAILURE:-0}" == 1 ]]; then exit 1; fi
if [[ "$*" == *' exec -T api '* && "${MOCK_UNHEALTHY:-0}" == 1 ]]; then exit 1; fi
''',
        "flock": 'test "${MOCK_LOCKED:-0}" != 1\n',
        "sleep": "exit 0\n",
    }
    for name, body in commands.items():
        path = bin_dir / name
        path.write_text("#!/usr/bin/env bash\nset -eu\n" + body, encoding="utf-8")
        path.chmod(0o755)
    log = tmp_path / "commands.log"
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "IMAGE_TAG": TAG,
        "DEPLOY_SHA": SHA,
        "MOCK_LOG": log.as_posix(),
        "MOCK_ARCHIVE": archive.as_posix(),
        "MOCK_BIN": bin_dir.as_posix(),
    }

    def run(**overrides):
        prefix = (
            'export PATH="$(cygpath -u "$MOCK_BIN"):$PATH"\n'
            if os.name == "nt" else 'export PATH="$MOCK_BIN:$PATH"\n'
        )
        result = subprocess.run(
            [bash, "-s"], input=prefix + SCRIPT, text=True, capture_output=True,
            cwd=tmp_path, env={**env, **overrides}, timeout=20,
        )
        return result, env_file.read_text(), log.read_text() if log.exists() else ""

    return run


def test_success_deploys_exact_commit_and_persists_verified_tag(deploy):
    result, settings, log = deploy()
    assert result.returncode == 0, result.stderr
    assert f"git archive {SHA} docker-compose.prod.yaml" in log
    assert "git checkout" not in log and "git pull" not in log
    assert f"IMAGE_TAG={TAG}" in settings and f"DEPLOY_SHA={SHA}" in settings
    assert "--no-build --pull never --wait" in log
    assert log.index(" pull ") < log.index(" up ") < log.index(" exec -T api ")


@pytest.mark.parametrize("overrides", [
    {"IMAGE_TAG": "latest"},
    {"DEPLOY_SHA": "b" * 40},
    {"MOCK_NON_MAIN": "1"},
    {"MOCK_LOCKED": "1"},
])
def test_invalid_release_or_lock_cannot_change_containers(deploy, overrides):
    result, settings, log = deploy(**overrides)
    assert result.returncode != 0
    assert "docker" not in log
    assert "IMAGE_TAG=old-release" in settings


def test_pull_failure_does_not_start_containers(deploy):
    result, settings, log = deploy(MOCK_PULL_FAILURE="1")
    assert result.returncode != 0
    assert " up " not in log
    assert "IMAGE_TAG=old-release" in settings


def test_failed_readiness_keeps_last_verified_tag(deploy):
    result, settings, log = deploy(MOCK_UNHEALTHY="1")
    assert result.returncode != 0
    assert " up " in log
    assert "IMAGE_TAG=old-release" in settings
    assert " exec -T frontend " not in log


def test_analytics_overlay_uses_same_release(deploy):
    result, settings, log = deploy(DEPLOY_ANALYTICS="1")
    assert result.returncode == 0, result.stderr
    assert "docker-compose.analytics.prod.yaml" in log
    assert "worker-data data-scheduler" in log
    assert f"MARKET_WORKER_IMAGE=alvarocareli/ragmatch-market-worker:{TAG}" in settings
