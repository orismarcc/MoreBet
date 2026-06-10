"""
APScheduler job — runs ingest_all_leagues daily at 03:00 UTC.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone="UTC")


def setup_scheduler(db_factory) -> None:
    from app.services.ingestion import ingest_all_leagues

    async def _job():
        db = db_factory()
        try:
            results = await ingest_all_leagues(db)
            for r in results:
                print(f"[Scheduler] {r}")
        finally:
            db.close()

    scheduler.add_job(
        _job,
        trigger=CronTrigger(hour=3, minute=0),
        id="daily_ingestion",
        replace_existing=True,
    )
    scheduler.start()
