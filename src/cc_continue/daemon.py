from __future__ import annotations

import asyncio
import logging
import signal

from cc_continue.orchestrator import Orchestrator, RunFn
from cc_continue.runner import execute
from cc_continue.storage import Storage

logger = logging.getLogger(__name__)


async def _run(db_path: str, run_fn: RunFn = execute) -> None:
    storage = Storage(db_path)
    orchestrator = Orchestrator(storage, run_fn=run_fn)
    await orchestrator.start_all()
    logger.info("cc-continue daemon started, db=%s, queues=%d", db_path, len(orchestrator.runtimes))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("cc-continue daemon shutting down")
    await orchestrator.stop_all()


def run_daemon(db_path: str, run_fn: RunFn = execute) -> None:
    asyncio.run(_run(db_path, run_fn))


def main() -> None:
    from cc_continue.cli import default_db_path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_daemon(str(default_db_path()))


if __name__ == "__main__":
    main()
