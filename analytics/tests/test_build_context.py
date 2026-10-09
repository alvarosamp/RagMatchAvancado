import tarfile

from analytics.build_image import write_context


def test_minimal_context_keeps_logging_code_and_excludes_secrets_and_outputs(tmp_path):
    sources = {
        "backend/app/logs/config.py": "logger = None",
        "backend/app/logs/logs/backend.app.log": "private log",
        "backend/app/.env": "SECRET_KEY=private",
        "analytics/Dockerfile": "FROM python:3.12-slim",
        "analytics/dbt/models/model.sql": "select 1",
        "analytics/dbt/logs/dbt.log": "private log",
        "analytics/dbt/target/manifest.json": "{}",
        "analytics/.validation/context.tar": "temporary",
    }
    for name, content in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    context = tmp_path / "context.tar"
    write_context(tmp_path, context)
    with tarfile.open(context) as archive:
        assert set(archive.getnames()) == {
            "backend/app/logs/config.py",
            "analytics/Dockerfile",
            "analytics/dbt/models/model.sql",
        }
        assert all(item.isfile() for item in archive.getmembers())
