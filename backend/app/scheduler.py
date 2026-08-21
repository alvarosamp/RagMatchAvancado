"""Single-process home for periodic integrations; run as the Compose scheduler service."""

from __future__ import annotations

import time
import os

from app.db.session import SessionLocal
from app.jobs.queue import recover_interrupted_jobs
from app.logs.config import logger
from app.services.email_monitor import start_email_monitor_loop
from app.services.pncp_radar_cache import start_daily_radar_refresh


def main() -> None:
    logger.info("[Scheduler] Iniciando rotinas periodicas.")
    start_daily_radar_refresh()
    start_email_monitor_loop()
    recovery_interval = max(30, int(os.getenv("JOB_RECOVERY_INTERVAL_SECONDS", "60")))
    while True:
        db = SessionLocal()
        try:
            summary = recover_interrupted_jobs(db)
            if any(summary.values()):
                logger.info("[Scheduler] Recuperacao de jobs: %s", summary)
        except Exception as exc:
            logger.warning("[Scheduler] Falha ao recuperar jobs: %s", exc, exc_info=True)
        finally:
            db.close()
        time.sleep(recovery_interval)


if __name__ == "__main__":
    main()
