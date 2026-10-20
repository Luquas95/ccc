import argparse
from datetime import datetime

import pytest

from ccc import goals, goals_cli, reviews
from ccc.models import (
    DeliveryMode, GoalPhase, GoalStatus, ItemStatus, PromptRun, ReviewStatus, RunStatus, Verdict,
)
from ccc.orchestrator import with_model
from ccc.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


@pytest.fixture
def queue(storage, tmp_path):
    # Legacy flags (None) = may run commands: ccc runs the check there.
    return storage.create_queue("shop", str(tmp_path), "s1")


def _finish_task(storage, goal, said="Done."):
    """The conversation did the goal's current task (a run + the item done)."""
    goal = storage.get_goal(goal.id)
    storage.insert_prompt_run(PromptRun(
        id=0, queue_id=goal.queue_id, queue_item_id=goal.item_id, prompt_text="t", started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS, result_text=said, git_commit="abcdef1234567",
    ))
    storage.set_item_status(goal.item_id, ItemStatus.DONE)


def _verdict(storage, goal, verdict, report):
    goal = storage.get_goal(goal.id)
    storage.update_review(goal.review_id, status=ReviewStatus.DONE, verdict=verdict, report=report)


def passing_check(command, cwd):
    return True, "ok"


async def _advance(storage, goal, check=passing_check):
    return await goals.advance(storage, storage.get_goal(goal.id), check_fn=check)


def test_start_queues_the_goal_as_the_first_task(storage, queue):
    goal = goals.start(storage, queue.id, "Expired tokens are rejected, with a test", "pytest -q", 3)
    item = storage.get_item(goal.item_id)
    assert "Expired tokens are rejected, with a test" in item.prompt_text
    assert (goal.round, goal.max_rounds, goal.phase) == (1, 3, GoalPhase.CODING)
    with pytest.raises(ValueError, match="already running"):
        goals.start(storage, queue.id, "another")
    with pytest.raises(ValueError, match="Describe the goal"):
        goals.start(storage, queue.id, "  ")  # checked before anything else


@pytest.mark.asyncio
async def test_a_round_waits_for_the_task_then_reviews_against_the_goal(storage, queue):
    goal = goals.start(storage, queue.id, "add() adds")
    assert (await _advance(storage, goal)).phase == GoalPhase.CODING  # task still queued
    _finish_task(storage, goal)
    goal = await _advance(storage, goal)
    review = storage.get_review(goal.review_id)
    assert goal.phase == GoalPhase.REVIEWING and review.goal_id == goal.id and review.model is None
    assert review.base_run_id == goal.base_run_id
    # The reviewer is told to judge the goal.
    prompt = reviews.prompt(storage, queue, review, "x")
    assert "add() adds" in prompt and "MEETS" in prompt
    _verdict(storage, goal, Verdict.PASS, "VERDICT: PASS — adds and tested")
    goal = await _advance(storage, goal)
    assert goal.status == GoalStatus.PASSED and goal.last_reason == "adds and tested"


@pytest.mark.asyncio
async def test_a_failed_review_becomes_the_next_rounds_task(storage, queue):
    goal = goals.start(storage, queue.id, "add() adds", max_rounds=5)
    _finish_task(storage, goal)
    await _advance(storage, goal)
    _verdict(storage, goal, Verdict.FAIL, "calc.py:2 subtracts\nVERDICT: FAIL — calc.py:2 subtracts")
    goal = await _advance(storage, goal)
    assert (goal.round, goal.phase, goal.status) == (2, GoalPhase.CODING, GoalStatus.RUNNING)
    task = storage.get_item(goal.item_id)
    assert "calc.py:2 subtracts" in task.prompt_text and "round 2 of 5" in task.prompt_text
    assert task.model is None  # no stronger model yet


@pytest.mark.asyncio
async def test_a_failing_check_fails_the_round_without_a_review(storage, queue):
    goal = goals.start(storage, queue.id, "tests pass", "pytest -q")
    _finish_task(storage, goal)
    goal = await _advance(storage, goal, check=lambda command, cwd: (False, "1 failed: test_add"))
    assert goal.round == 2 and goal.review_id is None
    assert "`pytest -q` failed" in storage.get_item(goal.item_id).prompt_text
    assert "1 failed: test_add" in storage.get_item(goal.item_id).prompt_text


@pytest.mark.asyncio
async def test_the_check_runs_only_where_claude_may_run_commands(storage, tmp_path):
    restricted = storage.create_queue("ro", str(tmp_path), "s2", launch_flags=["--permission-mode", "acceptEdits"])
    goal = goals.start(storage, restricted.id, "tests pass", "rm -rf /")
    _finish_task(storage, goal)
    ran = []
    goal = await _advance(storage, goal, check=lambda command, cwd: ran.append(command) or (False, ""))
    assert ran == [] and goal.phase == GoalPhase.REVIEWING


@pytest.mark.asyncio
async def test_the_same_failure_twice_is_stuck(storage, queue):
    goal = goals.start(storage, queue.id, "add() adds")
    for _round in range(2):
        _finish_task(storage, goal)
        await _advance(storage, goal)
        _verdict(storage, goal, Verdict.FAIL, "different wording each time\nVERDICT: FAIL — calc.py:2 subtracts")
        goal = await _advance(storage, goal)
    assert goal.status == GoalStatus.STUCK and "calc.py:2 subtracts" in goal.last_reason


@pytest.mark.asyncio
async def test_stronger_models_when_it_stalls_and_the_round_limit(storage, queue):
    goal = goals.start(storage, queue.id, "add() adds", max_rounds=4)
    models = []
    for n in range(1, 5):
        _finish_task(storage, goal)
        goal = await _advance(storage, goal)
        models.append((storage.get_review(goal.review_id).model, storage.get_item(goal.item_id).model))
        _verdict(storage, goal, Verdict.FAIL, f"VERDICT: FAIL — problem {n}")
        goal = await _advance(storage, goal)
    # (reviewer model, this round's coder model) for rounds 1–4
    assert models == [(None, None), (None, None), ("opus", None), ("opus", "opus")]
    assert goal.status == GoalStatus.LIMIT and goal.round == 4


@pytest.mark.asyncio
async def test_an_interactive_coder_keeps_its_model(storage, tmp_path, monkeypatch):
    monkeypatch.setattr(reviews, "managed_idle", lambda queue: True)
    live = storage.create_queue("live", str(tmp_path), "s3", delivery_mode=DeliveryMode.INTERACTIVE)
    goal = goals.start(storage, live.id, "x", max_rounds=6)
    storage.update_goal(goal.id, round=3)
    _finish_task(storage, goal)
    await _advance(storage, goal)
    _verdict(storage, goal, Verdict.FAIL, "VERDICT: FAIL — not yet")
    goal = await _advance(storage, goal)
    assert goal.round == 4 and storage.get_item(goal.item_id).model is None


@pytest.mark.asyncio
async def test_a_failed_task_ends_the_goal(storage, queue):
    goal = goals.start(storage, queue.id, "x")
    storage.set_item_status(goal.item_id, ItemStatus.FAILED)
    goal = await _advance(storage, goal)
    assert goal.status == GoalStatus.ERROR


def test_stop_skips_the_waiting_task(storage, queue):
    goal = goals.start(storage, queue.id, "x")
    assert goals.stop(storage, queue.id)
    assert storage.get_goal(goal.id).status == GoalStatus.STOPPED
    assert storage.get_item(goal.item_id).status == ItemStatus.SKIPPED
    assert not goals.stop(storage, queue.id)


def test_with_model_sets_or_replaces_the_model_flag():
    assert with_model(["--model", "sonnet", "-x"], "opus") == ["--model", "opus", "-x"]
    assert with_model(["--permission-mode", "plan"], "opus") == ["--permission-mode", "plan", "--model", "opus"]
    assert with_model(None, "opus") == ["--dangerously-skip-permissions", "--model", "opus"]


def test_run_check_reports_the_output_and_the_result(tmp_path):
    assert goals.run_check("echo fine", str(tmp_path)) == (True, "fine")
    passed, output = goals.run_check("echo broken >&2; exit 3", str(tmp_path))
    assert not passed and output == "broken"


def _cli(*argv):
    parser = argparse.ArgumentParser()
    goals_cli.add_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(["goal", *argv])


def test_cli_start_list_stop_and_wait(storage, queue, capsys):
    assert goals_cli.run(storage, _cli("start", "shop", "add() adds", "--check", "pytest -q", "--rounds", "3")) == 0
    [goal] = storage.list_goals(queue.id)
    assert (goal.check_command, goal.max_rounds) == ("pytest -q", 3)
    assert goals_cli.run(storage, _cli("list")) == 0
    assert "add() adds" in capsys.readouterr().out
    assert goals_cli.run(storage, _cli("stop", "shop")) == 0
    assert goals_cli.wait(storage, goal.id, lambda _s: None) == 1  # stopped
    storage.update_goal(goal.id, status=GoalStatus.PASSED)
    assert goals_cli.wait(storage, goal.id, lambda _s: None) == 0
