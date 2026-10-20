import argparse
from datetime import datetime, timedelta

import pytest

from ccc import routines, routines_cli
from ccc.models import DeliveryMode, ItemStatus, QueueStatus, RoutineTarget
from ccc.storage import Storage

NOW = datetime(2026, 10, 20, 17, 30)  # a Tuesday


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


@pytest.fixture
def queue(storage, tmp_path):
    return storage.create_queue("shop", str(tmp_path), "s1", delivery_mode=DeliveryMode.INTERACTIVE,
                                launch_flags=["--model", "opus"])


@pytest.mark.parametrize("kind,value,cron", [
    (routines.MINUTES, "30", "*/30 * * * *"),
    (routines.MINUTES, "1", "* * * * *"),
    (routines.HOURS, "2", "0 */2 * * *"),
    (routines.HOURS, "1", "0 * * * *"),
    (routines.DAILY, "18:00", "0 18 * * *"),
    (routines.WEEKDAYS, "7:05", "5 7 * * 1-5"),
    (routines.WEEKLY, "monday 08:00", "0 8 * * 1"),
    (routines.WEEKLY, "po 08:00", "0 8 * * 1"),
    (routines.WEEKLY, "Pátek 16:30", "30 16 * * 5"),
    (routines.CRON, " 0  22 * * * ", "0 22 * * *"),
])
def test_to_cron(kind, value, cron):
    assert routines.to_cron(kind, value) == cron


@pytest.mark.parametrize("kind,value,message", [
    (routines.MINUTES, "7", "doesn't divide 60"),
    (routines.MINUTES, "0", "whole number"),
    (routines.HOURS, "5", "doesn't divide 24"),
    (routines.DAILY, "25:00", "isn't a time"),
    (routines.WEEKLY, "someday 08:00", "isn't a day"),
    (routines.CRON, "0 0 31 2 *", "never runs"),
])
def test_bad_schedules(kind, value, message):
    with pytest.raises(ValueError, match=message):
        routines.to_cron(kind, value)


def test_describe():
    assert routines.describe(routines.DAILY, "18:00") == "every day at 18:00"
    assert routines.describe(routines.WEEKDAYS, "7:05") == "Mon–Fri at 07:05"
    assert routines.describe(routines.WEEKLY, "po 08:00") == "Mondays at 08:00"
    assert routines.describe(routines.MINUTES, "30") == "every 30 min"
    assert routines.describe(routines.CRON, "0 22 * * *") == "cron 0 22 * * *"


def test_add_sets_the_next_run_and_a_name(storage, queue):
    routine = routines.add(storage, queue.id, "", "Review today's changes\nin detail", routines.DAILY, "18:00",
                           now=NOW)
    assert routine.next_run_at == datetime(2026, 10, 20, 18, 0)
    assert routine.name == "Review today's changes"
    with pytest.raises(ValueError, match="needs a prompt"):
        routines.add(storage, queue.id, "x", "  ", routines.DAILY, "18:00")


def test_due_routine_queues_its_prompt_into_the_conversation(storage, queue):
    routine = routines.add(storage, queue.id, "nightly", "review", routines.DAILY, "18:00", now=NOW)
    assert routines.tick(storage, NOW) == []  # not yet
    fired = routines.tick(storage, NOW.replace(hour=18, minute=0, second=10))
    assert [status for _r, status in fired] == [routines.STATUS_QUEUED]
    items = storage.list_pending_items(queue.id)
    assert [(i.prompt_text, i.routine_id) for i in items] == [("review", routine.id)]
    again = storage.get_routine(routine.id)
    assert again.next_run_at == datetime(2026, 10, 21, 18, 0)
    assert again.last_status == routines.STATUS_QUEUED


def test_missed_runs_are_caught_up_once(storage, queue):
    routine = routines.add(storage, queue.id, "hourly", "check", routines.HOURS, "1", now=NOW)
    later = NOW + timedelta(hours=5, minutes=10)  # daemon was off for 5 runs
    assert len(routines.tick(storage, later)) == 1
    assert storage.routine_items_active(routine.id) == 1
    assert storage.get_routine(routine.id).next_run_at == later.replace(minute=0) + timedelta(hours=1)


def test_a_run_still_going_skips_the_next(storage, queue):
    routine = routines.add(storage, queue.id, "every 30", "check", routines.MINUTES, "30", now=NOW)
    routines.tick(storage, NOW + timedelta(minutes=30))
    routines.tick(storage, NOW + timedelta(minutes=60))
    r = storage.get_routine(routine.id)
    assert r.last_status == routines.STATUS_SKIPPED and r.skipped == 1
    assert storage.routine_items_active(routine.id) == 1
    item = storage.list_pending_items(queue.id)[0]
    storage.set_item_status(item.id, ItemStatus.DONE)
    routines.tick(storage, NOW + timedelta(minutes=90))
    assert storage.get_routine(routine.id).last_status == routines.STATUS_QUEUED


def test_fresh_target_starts_a_new_headless_conversation_and_archives_it_when_done(storage, queue):
    routine = routines.add(storage, queue.id, "audit", "audit it", routines.DAILY, "18:00",
                           RoutineTarget.FRESH, now=NOW)
    routines.tick(storage, NOW.replace(hour=18, minute=0))
    [spawned] = storage.routine_queues(routine.id)
    assert spawned.project_path == queue.project_path and spawned.launch_flags == ["--model", "opus"]
    assert spawned.delivery_mode == DeliveryMode.HEADLESS and spawned.session_id != queue.session_id
    assert spawned.name.startswith("audit · ")
    assert storage.list_pending_items(queue.id) == []  # not in the routine's own conversation
    assert routines.archive_finished(storage) == []  # still to run

    item = storage.list_pending_items(spawned.id)[0]
    storage.set_item_status(item.id, ItemStatus.DONE)
    assert routines.archive_finished(storage) == [spawned.id]
    assert storage.get_queue(spawned.id).archived


def test_a_blocked_fresh_conversation_stays_visible(storage, queue):
    routine = routines.add(storage, queue.id, "audit", "audit it", routines.DAILY, "18:00",
                           RoutineTarget.FRESH, now=NOW)
    routines.fire(storage, routine, NOW)
    [spawned] = storage.routine_queues(routine.id)
    storage.set_item_status(storage.list_pending_items(spawned.id)[0].id, ItemStatus.FAILED)
    storage.update_queue_status(spawned.id, QueueStatus.BLOCKED_ERROR)
    assert routines.archive_finished(storage) == []


def test_nothing_runs_for_an_archived_conversation(storage, queue):
    routine = routines.add(storage, queue.id, "nightly", "review", routines.DAILY, "18:00", now=NOW)
    storage.set_queue_archived(queue.id, True)
    assert routines.fire(storage, routine, NOW) == routines.STATUS_ARCHIVED
    assert storage.list_pending_items(queue.id) == []


def test_turning_on_again_waits_for_the_next_time(storage, queue):
    routine = routines.add(storage, queue.id, "nightly", "review", routines.DAILY, "18:00", now=NOW)
    routines.set_enabled(storage, routine.id, False, NOW)
    assert routines.tick(storage, NOW + timedelta(days=3)) == []
    routines.set_enabled(storage, routine.id, True, NOW + timedelta(days=3))
    assert storage.get_routine(routine.id).next_run_at == datetime(2026, 10, 23, 18, 0)


def test_deleting_the_conversation_deletes_its_routines(storage, queue):
    routines.add(storage, queue.id, "nightly", "review", routines.DAILY, "18:00", now=NOW)
    storage.delete_queue(queue.id)
    assert storage.list_routines() == []


def _cli(*argv):
    parser = argparse.ArgumentParser()
    routines_cli.add_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(["routine", *argv])


def test_cli_add_list_run_off_remove(storage, queue, capsys):
    assert routines_cli.run(storage, _cli("add", "shop", "review", "--weekdays", "18:00", "--name", "evening")) == 0
    [routine] = storage.list_routines()
    assert (routine.schedule_kind, routine.cron, routine.target) == (routines.WEEKDAYS, "0 18 * * 1-5",
                                                                     RoutineTarget.SAME)
    assert routines_cli.run(storage, _cli("list")) == 0
    assert "evening" in capsys.readouterr().out
    assert routines_cli.run(storage, _cli("run", "evening")) == 0
    assert storage.routine_items_active(routine.id) == 1
    assert routines_cli.run(storage, _cli("off", str(routine.id))) == 0
    assert not storage.get_routine(routine.id).enabled
    assert routines_cli.run(storage, _cli("remove", "evening")) == 0
    assert storage.list_routines() == []


@pytest.mark.parametrize("argv,kind,value", [
    (("--every", "30m"), routines.MINUTES, "30"),
    (("--every", "2h"), routines.HOURS, "2"),
    (("--hourly",), routines.HOURS, "1"),
    (("--daily",), routines.DAILY, "09:00"),
    (("--on", "friday 16:00"), routines.WEEKLY, "friday 16:00"),
    (("--cron", "0 22 * * *"), routines.CRON, "0 22 * * *"),
])
def test_cli_schedules(storage, queue, argv, kind, value):
    assert routines_cli.run(storage, _cli("add", str(queue.id), "p", *argv, "--fresh")) == 0
    [routine] = storage.list_routines()
    assert (routine.schedule_kind, routine.schedule_value, routine.target) == (kind, value, RoutineTarget.FRESH)


def test_cli_refuses_a_bad_schedule_or_conversation(storage, queue, capsys):
    assert routines_cli.run(storage, _cli("add", "shop", "p", "--every", "7m")) == 1
    assert routines_cli.run(storage, _cli("add", "nope", "p", "--daily")) == 1
    assert "No single active conversation" in capsys.readouterr().out
    assert storage.list_routines() == []
