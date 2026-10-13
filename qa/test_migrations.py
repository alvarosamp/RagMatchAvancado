import subprocess


def test_upgrades_from_commercial_and_technical_releases_preserve_records():
    result = subprocess.run(
        ["docker", "compose", "-f", "qa/compose.yaml", "exec", "-T", "api", "python", "/qa/migration_upgrade_checks.py"],
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
