from __future__ import annotations

import asyncio
import logging
import signal

from ccc import i18n
from ccc.backup import daily_backup, default_backup_dir
from ccc.heartbeat import HEARTBEAT_SECONDS, beat
from ccc.notify import Notifier
from ccc.analytics_archive import ARCHIVE_CHECK_SECONDS, archive, configured_folder
from ccc.orchestrator import Orchestrator, RunFn
from ccc.runner import execute
from ccc.session_usage import USAGE_POLL_SECONDS, UsageCollector
from ccc.storage import Storage

logger = logging.getLogger(__name__)


async def heartbeat_loop(storage: Storage, interval: float = HEARTBEAT_SECONDS) -> None:
    while True:
        try:
            beat(storage)
            # Notifications and notes follow the language set in the TUI.
            i18n.load(storage)
        except Exception:  # a locked DB moment must not kill the loop
            logger.exception("heartbeat write failed")
        await asyncio.sleep(interval)


BACKUP_CHECK_SECONDS = 3600.0


async def backup_loop(db_path: str, out_dir, interval: float = BACKUP_CHECK_SECONDS) -> None:
    """Check hourly; daily_backup itself makes at most one backup a day."""
    while True:
        try:
            path = await asyncio.to_thread(daily_backup, db_path, out_dir)
            if path is not None:
                logger.info("database backed up to %s", path)
        except Exception:
            logger.exception("database backup failed")
        await asyncio.sleep(interval)


async def usage_loop(storage: Storage, interval: float = USAGE_POLL_SECONDS) -> None:
    """Token usage of remote-control conversations, from their transcripts."""
    collector = UsageCollector()
    while True:
        try:
            await asyncio.to_thread(collector.collect, storage)
        except Exception:
            logger.exception("reading remote-control token usage failed")
        await asyncio.sleep(interval)


async def archive_loop(storage: Storage, interval: float = ARCHIVE_CHECK_SECONDS) -> None:
    """Hourly: archive months that have ended, when a folder is set."""
    while True:
        try:
            folder = configured_folder(storage)
            added = await asyncio.to_thread(archive, storage, folder) if folder else []
            for year, month in added:
                logger.info("Analytics: %04d-%02d archived to %s", year, month, folder)
        except Exception:
            logger.exception("archiving analytics failed")
        await asyncio.sleep(interval)


ROUTINE_CHECK_SECONDS = 20.0


async def routines_loop(storage: Storage, interval: float = ROUTINE_CHECK_SECONDS) -> None:
    """Queue the routines that are due (ccc.routines); the queues' own
    runtimes pick their tasks up."""
    from ccc import routines

    while True:
        try:
            for routine, status in await asyncio.to_thread(routines.tick, storage):
                logger.info("routine %d (%s): %s", routine.id, routine.name, status)
        except Exception:
            logger.exception("running routines failed")
        await asyncio.sleep(interval)


async def _run(db_path: str, run_fn: RunFn = execute) -> None:
    storage = Storage(db_path)
    i18n.load(storage)
    orchestrator = Orchestrator(storage, run_fn=run_fn, notifier=Notifier(storage))
    await orchestrator.start_all()
    logger.info("ccc daemon started, db=%s, queues=%d", db_path, len(orchestrator.runtimes))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    heartbeat = asyncio.create_task(heartbeat_loop(storage))
    backups = asyncio.create_task(backup_loop(db_path, default_backup_dir(db_path)))
    usage = asyncio.create_task(usage_loop(storage))
    archives = asyncio.create_task(archive_loop(storage))
    scheduled = asyncio.create_task(routines_loop(storage))
    await stop_event.wait()
    logger.info("ccc daemon shutting down")
    heartbeat.cancel()
    backups.cancel()
    usage.cancel()
    archives.cancel()
    scheduled.cancel()
    await orchestrator.stop_all()


def run_daemon(db_path: str, run_fn: RunFn = execute) -> None:
    asyncio.run(_run(db_path, run_fn))


def main() -> None:
    from ccc.cli import default_db_path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_daemon(str(default_db_path()))


if __name__ == "__main__":
    main()
