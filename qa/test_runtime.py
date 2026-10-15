import subprocess


def test_production_orm_preserves_isolation_after_commit_and_rollback():
    result = subprocess.run([
        "docker", "compose", "-f", "qa/compose.yaml", "exec", "-T", "api",
        "coverage", "run", "--source=app", "--data-file=/reports/.coverage.runtime",
        "/qa/runtime_checks.py",
    ], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
