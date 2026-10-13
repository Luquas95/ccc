from __future__ import annotations

import asyncio
import logging
import signal

from ccc.orchestrator import Orchestrator, RunFn
from ccc.runner import execute
from ccc.storage import Storage

logger = logging.getLogger(__name__)


async def _run(db_path: str, run_fn: RunFn = execute) -> None:
    storage = Storage(db_path)
    orchestrator = Orchestrator(storage, run_fn=run_fn)
    await orchestrator.start_all()
    logger.info("ccc daemon started, db=%s, queues=%d", db_path, len(orchestrator.runtimes))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("ccc daemon shutting down")
    await orchestrator.stop_all()


def run_daemon(db_path: str, run_fn: RunFn = execute) -> None:
    asyncio.run(_run(db_path, run_fn))


def main() -> None:
    from ccc.cli import default_db_path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_daemon(str(default_db_path()))


if __name__ == "__main__":
    main()
