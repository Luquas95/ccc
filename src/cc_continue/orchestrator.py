from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from cc_continue.models import ItemStatus, PromptRun, Queue, QueueStatus, RunStatus
from cc_continue.retry import next_backoff_seconds, parse_reset_time
from cc_continue.runner import RunResult, execute
from cc_continue.storage import Storage

RunFn = Callable[[str, str, str, bool], Awaitable[RunResult]]

# How often an idle/blocked queue re-checks storage even without an
# in-process notify(). This is what makes it safe for another process (the
# TUI, or `cc-continue add`) to enqueue a prompt or clear a blocked queue
# without the daemon needing any cross-process signaling mechanism.
POLL_INTERVAL_SECONDS = 5.0


def enqueue_prompt(storage: Storage, project_path: str, prompt_text: str, name: str | None = None) -> Queue:
    """Add a prompt to a project's queue, creating the queue if needed.
    Pure storage operation — does not start or notify any execution
    engine. Safe to call from a process that never runs an Orchestrator
    (the TUI, the `cc-continue add` CLI) alongside a daemon process that
    does; the daemon picks the new row up on its next poll."""
    queue = storage.get_queue_by_path(project_path)
    if queue is None:
        queue = storage.create_queue(
            name or Path(project_path).name or project_path,
            project_path,
            str(uuid.uuid4()),
        )
    storage.add_queue_item(queue.id, prompt_text)
    return queue


class QueueRuntime:
    def __init__(self, storage: Storage, queue: Queue, run_fn: RunFn = execute):
        self.storage = storage
        self.queue = queue
        self.run_fn = run_fn
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._backoff_seconds: int | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def notify(self) -> None:
        self._wake.set()

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while True:
            queue = self.storage.get_queue(self.queue.id)
            self.queue = queue

            if queue.status == QueueStatus.BLOCKED_ERROR:
                await self._wait_for_wake_or_poll(POLL_INTERVAL_SECONDS)
                continue

            item = self.storage.claim_next_pending_item(queue.id)
            if item is None:
                self.storage.update_queue_status(queue.id, QueueStatus.IDLE)
                await self._wait_for_wake_or_poll(POLL_INTERVAL_SECONDS)
                continue

            self.storage.update_queue_status(queue.id, QueueStatus.RUNNING)

            resume = self._has_run_before()
            started_at = datetime.now()
            result = await self.run_fn(queue.project_path, queue.session_id, item.prompt_text, resume)
            finished_at = datetime.now()

            self.storage.insert_prompt_run(
                PromptRun(
                    id=0,
                    queue_id=queue.id,
                    queue_item_id=item.id,
                    prompt_text=item.prompt_text,
                    started_at=started_at,
                    finished_at=finished_at,
                    status=result.status,
                    cost_usd=result.cost_usd,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cache_read_tokens=result.cache_read_tokens,
                    cache_creation_tokens=result.cache_creation_tokens,
                    duration_ms=result.duration_ms,
                    num_turns=result.num_turns,
                    result_text=result.result_text,
                    error_text=result.error_text,
                )
            )

            if result.status == RunStatus.SUCCESS:
                self.storage.set_item_status(item.id, ItemStatus.DONE)
                self._backoff_seconds = None
                continue

            if result.status == RunStatus.RATE_LIMITED:
                self.storage.set_item_status(item.id, ItemStatus.PENDING)
                retry_at = parse_reset_time(result.error_text or "")
                if retry_at is None:
                    self._backoff_seconds = next_backoff_seconds(self._backoff_seconds)
                    retry_at = datetime.fromtimestamp(datetime.now().timestamp() + self._backoff_seconds)
                self.storage.update_queue_status(
                    queue.id, QueueStatus.WAITING_RETRY, next_retry_at=retry_at
                )
                delay = max((retry_at - datetime.now()).total_seconds(), 0)
                await self._wait_for_wake_or_poll(delay)
                continue

            self.storage.set_item_status(item.id, ItemStatus.FAILED)
            self.storage.update_queue_status(
                queue.id, QueueStatus.BLOCKED_ERROR, last_error=result.error_text
            )

    def _has_run_before(self) -> bool:
        return len(self.storage.runs_for_queue(self.queue.id)) > 0

    async def _wait_for_wake_or_poll(self, timeout: float) -> None:
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=timeout)
            self._wake.clear()
        except asyncio.TimeoutError:
            pass


class Orchestrator:
    def __init__(self, storage: Storage, run_fn: RunFn = execute):
        self.storage = storage
        self.run_fn = run_fn
        self.runtimes: dict[int, QueueRuntime] = {}
        self._discovery_task: asyncio.Task | None = None

    async def start_all(self) -> None:
        """Start executing every existing queue, then keep discovering new
        ones (created later by `cc-continue add` or the TUI, in this or
        another process) in the background. Only ONE process (the daemon)
        should ever call this: it resets any item left 'running' back to
        'pending' as crash recovery, which would wrongly steal an item
        that's legitimately mid-execution in an already-running daemon.
        Other processes (the TUI, `cc-continue add`) must only use
        enqueue_prompt() — never construct an Orchestrator and call this."""
        self.storage.reset_running_items_to_pending()
        for queue in self.storage.list_queues():
            self._start_runtime(queue)
        self._discovery_task = asyncio.create_task(self._discover_new_queues_loop())

    async def _discover_new_queues_loop(self) -> None:
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            for queue in self.storage.list_queues():
                if queue.id not in self.runtimes:
                    self._start_runtime(queue)

    def _start_runtime(self, queue: Queue) -> QueueRuntime:
        runtime = QueueRuntime(self.storage, queue, self.run_fn)
        self.runtimes[queue.id] = runtime
        runtime.start()
        return runtime

    def get_or_create_queue(self, project_path: str, name: str | None = None) -> Queue:
        existing = self.storage.get_queue_by_path(project_path)
        if existing:
            if existing.id not in self.runtimes:
                self._start_runtime(existing)
            return existing
        queue = self.storage.create_queue(
            name or project_path.rstrip("/").split("/")[-1],
            project_path,
            str(uuid.uuid4()),
        )
        self._start_runtime(queue)
        return queue

    def add_prompt(self, project_path: str, prompt_text: str) -> None:
        queue = self.get_or_create_queue(project_path)
        self.storage.add_queue_item(queue.id, prompt_text)
        self.runtimes[queue.id].notify()

    async def stop_all(self) -> None:
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        await asyncio.gather(*(rt.stop() for rt in self.runtimes.values()))
