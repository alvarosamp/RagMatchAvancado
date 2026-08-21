from __future__ import annotations

import os

from fastapi import FastAPI

from app.core.security import configure_security
from app.core.startup import register_startup_tasks
from app.routers import register_routers


def create_app() -> FastAPI:
    app_env = os.getenv("APP_ENV", "development").lower()
    is_production = app_env in {"prod", "production"}

    app = FastAPI(
        title="Edital Matcher API",
        version="0.5.0",
        description="Matching inteligente de produtos contra editais de licitacao",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    configure_security(app)
    register_routers(app)
    register_startup_tasks(app)

    return app


app = create_app()
