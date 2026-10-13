from __future__ import annotations

import asyncio
import logging
import signal

from ccc.heartbeat import HEARTBEAT_SECONDS, beat
from ccc.orchestrator import Orchestrator, RunFn
from ccc.runner import execute
from ccc.storage import Storage

logger = logging.getLogger(__name__)


async def heartbeat_loop(storage: Storage, interval: float = HEARTBEAT_SECONDS) -> None:
    while True:
        try:
            beat(storage)
        except Exception:  # a locked DB moment must not kill the loop
            logger.exception("heartbeat write failed")
        await asyncio.sleep(interval)


async def _run(db_path: str, run_fn: RunFn = execute) -> None:
    storage = Storage(db_path)
    orchestrator = Orchestrator(storage, run_fn=run_fn)
    await orchestrator.start_all()
    logger.info("ccc daemon started, db=%s, queues=%d", db_path, len(orchestrator.runtimes))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    heartbeat = asyncio.create_task(heartbeat_loop(storage))
    await stop_event.wait()
    logger.info("ccc daemon shutting down")
    heartbeat.cancel()
    await orchestrator.stop_all()


def run_daemon(db_path: str, run_fn: RunFn = execute) -> None:
    asyncio.run(_run(db_path, run_fn))


def main() -> None:
    from ccc.cli import default_db_path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_daemon(str(default_db_path()))


if __name__ == "__main__":
    main()
