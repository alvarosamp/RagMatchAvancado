from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import configure_security


def test_csrf_frontend_origin_is_also_a_trusted_proxy_host():
    with patch.dict(
        "os.environ",
        {
            "ALLOWED_HOSTS": "api.example.com",
            "CSRF_TRUSTED_ORIGINS": "https://app.example.com",
        },
        clear=False,
    ):
        app = FastAPI()
        configure_security(app)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        response = TestClient(app).get(
            "/health",
            headers={"host": "app.example.com"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
