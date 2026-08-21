from __future__ import annotations

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.jobs.router import router as jobs_router
from app.routers.analysis import router as analysis_router
from app.routers.analysis_dashboard import router as analysis_dashboard_router
from app.routers.analytics import router as analytics_router
from app.routers.bid_robot import router as bid_robot_router
from app.routers.crm import router as crm_router
from app.routers.datasheets import router as datasheets_router
from app.routers.documents import router as documents_router
from app.routers.editais import router as editais_router
from app.routers.edital_locks import router as edital_locks_router
from app.routers.export import router as export_router
from app.routers.health import router as health_router
from app.routers.market import router as market_router
from app.routers.ops import router as ops_router
from app.routers.pncp import router as pncp_router
from app.routers.reports import router as reports_router
from app.routers.switches import router as switches_router


ROUTERS = (
    health_router,
    auth_router,
    crm_router,
    jobs_router,
    ops_router,
    reports_router,
    analysis_router,
    analysis_dashboard_router,
    documents_router,
    switches_router,
    market_router,
    bid_robot_router,
    editais_router,
    edital_locks_router,
    pncp_router,
    export_router,
    analytics_router,
    datasheets_router,
)


def register_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router)
