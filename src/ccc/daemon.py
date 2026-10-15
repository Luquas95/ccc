from __future__ import annotations

import asyncio
import logging
import signal

from ccc.backup import daily_backup, default_backup_dir
from ccc.heartbeat import HEARTBEAT_SECONDS, beat
from ccc.notify import Notifier
from ccc.obsidian_export import EXPORT_INTERVAL_SECONDS, configured_folder, export
from ccc.orchestrator import Orchestrator, RunFn
from ccc.runner import execute
from ccc.session_usage import USAGE_POLL_SECONDS, UsageCollector
from ccc.storage import Storage

logger = logging.getLogger(__name__)


async def heartbeat_loop(storage: Storage, interval: float = HEARTBEAT_SECONDS) -> None:
    while True:
        try:
            beat(storage)
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


async def obsidian_loop(storage: Storage, interval: float = EXPORT_INTERVAL_SECONDS) -> None:
    """Token history as Markdown notes for Obsidian, when a folder is set."""
    while True:
        folder = configured_folder(storage)
        if folder:
            try:
                written = await asyncio.to_thread(export, storage, folder)
                if written:
                    logger.info("Obsidian export: %d note(s) updated in %s", written, folder)
            except Exception:
                logger.exception("Obsidian export failed")
        await asyncio.sleep(interval)


async def _run(db_path: str, run_fn: RunFn = execute) -> None:
    storage = Storage(db_path)
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
    obsidian = asyncio.create_task(obsidian_loop(storage))
    await stop_event.wait()
    logger.info("ccc daemon shutting down")
    heartbeat.cancel()
    backups.cancel()
    usage.cancel()
    obsidian.cancel()
    await orchestrator.stop_all()


def run_daemon(db_path: str, run_fn: RunFn = execute) -> None:
    asyncio.run(_run(db_path, run_fn))


def main() -> None:
    from ccc.cli import default_db_path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_daemon(str(default_db_path()))


if __name__ == "__main__":
    main()
