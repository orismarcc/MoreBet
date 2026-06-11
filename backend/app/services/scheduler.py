"""
APScheduler jobs — keep data fresh automatically:
  - full league refresh every 6 hours (rate-limit safe, ~30s per run)
  - an immediate bootstrap run when the database has no leagues yet, so a
    fresh deploy populates itself without anyone clicking "Atualizar".
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def setup_scheduler(db_factory) -> None:
    from app.models.orm import League
    from app.services.ingestion import ingest_all_leagues

    async def _job():
        db = db_factory()
        try:
            results = await ingest_all_leagues(db)
            for r in results:
                logger.info("[Scheduler] %s", r)
        finally:
            db.close()

    # Every 6 hours keeps tournament data (World Cup has multiple matchdays
    # per day) acceptably fresh without stressing the free-tier API.
    scheduler.add_job(
        _job,
        trigger=CronTrigger(hour="0,6,12,18", minute=0),
        id="periodic_ingestion",
        replace_existing=True,
    )

    # Bootstrap: empty database → ingest right away (runs in the scheduler's
    # event loop a few seconds after startup, so boot isn't blocked).
    db = db_factory()
    try:
        needs_bootstrap = db.query(League).first() is None
    except Exception:
        needs_bootstrap = False  # tables may not exist yet on very first boot
    finally:
        db.close()

    if needs_bootstrap:
        logger.info("[Scheduler] empty database — scheduling immediate bootstrap ingestion")
        scheduler.add_job(_job, trigger=DateTrigger(), id="bootstrap_ingestion")

    scheduler.start()
