import argparse
from datetime import datetime, timedelta, timezone

import pytest

from ccc import reviews, reviews_cli
from ccc.models import ItemStatus, PromptRun, QueueStatus, ReviewStatus, RunStatus, Verdict
from ccc.runner import RunResult
from ccc.storage import Storage
from ccc.usage_api import ProUsage, WindowUsage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


@pytest.fixture
def queue(storage, tmp_path):
    return storage.create_queue("shop", str(tmp_path), "s1", launch_flags=["--model", "sonnet"])


def _task_run(storage, queue, text="add a login page", commit="abc123def4567", said="Added login.") -> int:
    return storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue.id, queue_item_id=None, prompt_text=text, started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS, result_text=said, git_commit=commit,
    ))


class FakeReviewer:
    def __init__(self, *reports, status=RunStatus.SUCCESS):
        self.reports = list(reports)
        self.status = status
        self.calls = []

    async def __call__(self, project_path, prompt, model):
        self.calls.append((project_path, prompt, model))
        report = self.reports.pop(0) if self.reports else ""
        return RunResult(status=self.status, result_text=report, error_text="boom" if self.status != RunStatus.SUCCESS
                         else None, input_tokens=100, output_tokens=20,
                         model_usage={"claude-sonnet": {"input_tokens": 100, "output_tokens": 20,
                                                        "cache_read_tokens": 0, "cache_creation_tokens": 0}})


def _no_usage():
    return None


@pytest.mark.parametrize("text,verdict,reason", [
    ("All good.\nVERDICT: PASS — tests cover the expiry path", Verdict.PASS, "tests cover the expiry path"),
    ("**VERDICT: FAIL** - auth.py:12 accepts expired tokens", Verdict.FAIL, "auth.py:12 accepts expired tokens"),
    ("verdict: partial — couldn't run the e2e suite", Verdict.PARTIAL, "couldn't run the e2e suite"),
    ("VERDICT: FAIL — first\nfixed it\nVERDICT: PASS — later", Verdict.PASS, "later"),  # the last one counts
    ("no verdict here", None, ""),
])
def test_parse_verdict(text, verdict, reason):
    assert reviews.parse_verdict(text) == (verdict, reason)


def test_the_reviewer_can_only_read_and_isnt_saved():
    cmd = reviews.command("check it", "opus")
    assert cmd[:3] == ["claude", "-p", "check it"]
    assert "--no-session-persistence" in cmd
    assert cmd[cmd.index("--tools") + 1] == "Read,Grep,Glob"  # no Bash: it can't run anything
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[cmd.index("--setting-sources") + 1] == "user"  # none of the reviewed project's settings
    assert cmd[-2:] == ["--model", "opus"]
    assert "--model" not in reviews.command("check it", None)


def test_model_follows_the_setting_or_the_conversation(storage, queue):
    assert reviews.model_for(storage, queue) == "sonnet"
    storage.set_setting(reviews.MODEL_KEY, "opus")
    assert reviews.model_for(storage, queue) == "opus"


def test_one_review_at_a_time(storage, queue):
    reviews.request(storage, queue.id)
    with pytest.raises(ValueError, match="already waiting"):
        reviews.request(storage, queue.id)


@pytest.mark.asyncio
async def test_reviews_the_commits_since_the_last_review(storage, queue):
    _task_run(storage, queue)
    review = reviews.request(storage, queue.id, "check the error paths")
    fake = FakeReviewer("Looks right.\nVERDICT: PASS — login works")
    done = await reviews.tick(storage, fake, usage_fn=_no_usage)
    assert [r.id for r in done] == [review.id]
    review = storage.get_review(review.id)
    assert (review.status, review.verdict) == (ReviewStatus.DONE, Verdict.PASS)
    project, prompt, model = fake.calls[0]
    assert "abc123def456" in prompt and "add a login page" in prompt and "Added login." in prompt
    assert "check the error paths" in prompt and model == "sonnet"
    # Its tokens count like a task's, as a run of the review.
    [run] = [r for r in storage.runs_for_queue(queue.id) if r.review_id == review.id]
    assert run.input_tokens == 100 and run.queue_item_id is None
    # The next review starts after it: nothing new, no model call.
    nxt = reviews.request(storage, queue.id)
    await reviews.tick(storage, fake, usage_fn=_no_usage)
    assert storage.get_review(nxt.id).status == ReviewStatus.NOTHING
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_nothing_to_review_calls_no_model(storage, queue):
    review = reviews.request(storage, queue.id)
    fake = FakeReviewer()
    await reviews.tick(storage, fake, usage_fn=_no_usage)
    assert storage.get_review(review.id).status == ReviewStatus.NOTHING and fake.calls == []


@pytest.mark.asyncio
async def test_waits_while_the_conversation_works(storage, queue):
    _task_run(storage, queue)
    storage.add_queue_item(queue.id, "next task")
    review = reviews.request(storage, queue.id)
    fake = FakeReviewer("VERDICT: PASS — ok")
    assert await reviews.tick(storage, fake, usage_fn=_no_usage) == []
    storage.update_queue_status(queue.id, QueueStatus.RUNNING)
    storage.set_item_status(storage.list_pending_items(queue.id)[0].id, ItemStatus.DONE)
    assert await reviews.tick(storage, fake, usage_fn=_no_usage) == []
    assert storage.get_review(review.id).status == ReviewStatus.PENDING and fake.calls == []


@pytest.mark.asyncio
async def test_waits_for_the_usage_limit(storage, queue):
    _task_run(storage, queue)
    review = reviews.request(storage, queue.id)
    resets = datetime.now(timezone.utc) + timedelta(hours=2)
    full = ProUsage(five_hour=WindowUsage(100.0, resets), seven_day=None, per_model=[])
    fake = FakeReviewer("VERDICT: PASS — ok")
    await reviews.tick(storage, fake, usage_fn=lambda: full)
    review = storage.get_review(review.id)
    assert review.status == ReviewStatus.PENDING and review.not_before is not None and fake.calls == []
    # Not before that time.
    await reviews.tick(storage, fake, usage_fn=_no_usage)
    assert fake.calls == []


@pytest.mark.asyncio
async def test_rate_limited_review_waits_and_failed_one_errors(storage, queue):
    _task_run(storage, queue)
    review = reviews.request(storage, queue.id)
    await reviews.tick(storage, FakeReviewer(status=RunStatus.RATE_LIMITED), usage_fn=_no_usage)
    review = storage.get_review(review.id)
    assert review.status == ReviewStatus.PENDING and review.not_before is not None
    storage.update_review(review.id, not_before=None)
    await reviews.tick(storage, FakeReviewer(status=RunStatus.ERROR), usage_fn=_no_usage)
    assert storage.get_review(review.id).status == ReviewStatus.ERROR


@pytest.mark.asyncio
async def test_no_verdict_line_is_an_error(storage, queue):
    _task_run(storage, queue)
    review = reviews.request(storage, queue.id)
    await reviews.tick(storage, FakeReviewer("I looked around."), usage_fn=_no_usage)
    review = storage.get_review(review.id)
    assert review.status == ReviewStatus.ERROR and review.report == "I looked around."


@pytest.mark.asyncio
async def test_until_it_passes_sends_findings_back_and_reviews_again(storage, queue):
    _task_run(storage, queue)
    first = reviews.request(storage, queue.id, until_pass=True, max_rounds=3)
    fake = FakeReviewer("VERDICT: FAIL — auth.py:12 accepts expired tokens", "VERDICT: PASS — fixed")
    await reviews.tick(storage, fake, usage_fn=_no_usage)
    first = storage.get_review(first.id)
    fix = storage.get_item(first.fix_item_id)
    assert "auth.py:12 accepts expired tokens" in fix.prompt_text and fix.status == ItemStatus.PENDING
    [second] = storage.list_reviews(queue.id, ReviewStatus.PENDING)
    assert (second.round, second.loop_id, second.base_run_id) == (2, first.id, first.base_run_id)
    # The fix is still queued: round 2 waits.
    await reviews.tick(storage, fake, usage_fn=_no_usage)
    assert len(fake.calls) == 1
    storage.set_item_status(fix.id, ItemStatus.DONE)
    _task_run(storage, queue, "fix", "fedcba9876543", "Fixed the expiry check.")
    await reviews.tick(storage, fake, usage_fn=_no_usage)
    second = storage.get_review(second.id)
    assert second.verdict == Verdict.PASS
    # Round 2 re-checks the whole loop's work, not just the fix.
    assert "abc123def456" in fake.calls[1][1] and "fedcba987654" in fake.calls[1][1] and "round 2" in fake.calls[1][1]
    assert storage.list_reviews(queue.id, ReviewStatus.PENDING) == []


@pytest.mark.asyncio
async def test_the_round_limit_ends_the_loop(storage, queue):
    _task_run(storage, queue)
    review = reviews.request(storage, queue.id, until_pass=True, max_rounds=1)
    await reviews.tick(storage, FakeReviewer("VERDICT: FAIL — still broken"), usage_fn=_no_usage)
    assert storage.list_reviews(queue.id, ReviewStatus.PENDING) == []
    assert storage.get_review(review.id).fix_item_id is None


def test_stop_drops_a_waiting_review(storage, queue):
    review = reviews.request(storage, queue.id)
    assert reviews.stop(storage, queue.id) == 1
    assert storage.get_review(review.id).status == ReviewStatus.STOPPED
    reviews.request(storage, queue.id)  # a new one may be asked for


def test_apply_queues_the_findings(storage, queue):
    review = reviews.request(storage, queue.id)
    storage.update_review(review.id, status=ReviewStatus.DONE, verdict=Verdict.PARTIAL, report="couldn't run e2e")
    item = reviews.apply(storage, storage.get_review(review.id))
    assert "couldn't run e2e" in item.prompt_text and "PARTIAL" in item.prompt_text
    assert storage.get_review(review.id).fix_item_id == item.id


def _cli(*argv):
    parser = argparse.ArgumentParser()
    reviews_cli.add_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(["review", *argv])


def test_cli_start_list_show_stop(storage, queue, capsys):
    assert reviews_cli.run(storage, _cli("start", "shop", "the error paths")) == 0
    [review] = storage.list_reviews(queue.id)
    assert review.instructions == "the error paths"
    assert reviews_cli.run(storage, _cli("list")) == 0
    assert "pending" in capsys.readouterr().out
    storage.update_review(review.id, status=ReviewStatus.DONE, verdict=Verdict.FAIL, report="x.py:1 wrong")
    assert reviews_cli.run(storage, _cli("show", str(review.id))) == 0
    assert "x.py:1 wrong" in capsys.readouterr().out
    assert reviews_cli.run(storage, _cli("stop", "shop")) == 0


@pytest.mark.parametrize("status,verdict,code", [
    (ReviewStatus.DONE, Verdict.PASS, 0), (ReviewStatus.DONE, Verdict.FAIL, 3),
    (ReviewStatus.DONE, Verdict.PARTIAL, 4), (ReviewStatus.NOTHING, None, 0), (ReviewStatus.ERROR, None, 1),
])
def test_cli_wait_exit_codes(storage, queue, status, verdict, code):
    review = reviews.request(storage, queue.id)
    polls = []

    def sleep(_seconds):
        polls.append(1)
        storage.update_review(review.id, status=status, verdict=verdict)

    assert reviews_cli.wait(storage, review.id, sleep) == code
    assert polls == [1]


def _git(cwd, *args):
    import subprocess

    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "init")
    return path


def test_review_diff_of_commits_and_of_uncommitted_changes(repo):
    from ccc import gitops

    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    _git(repo, "commit", "-qam", "break it")
    head = gitops._git(str(repo), "rev-parse", "HEAD").stdout.strip()
    diff = gitops.review_diff(str(repo), [head, "--output=/tmp/x"])  # an option is never passed on
    assert "-    return a + b" in diff and "+    return a - b" in diff
    (repo / "calc.py").write_text("def add(a, b):\n    return b + a\n")
    (repo / "new.py").write_text("x = 1\n")
    diff = gitops.review_diff(str(repo), [])
    assert "+    return b + a" in diff and "New files (read them whole):\nnew.py" in diff


def test_review_diff_refuses_an_unsafe_repo_config(repo):
    from ccc import gitops

    _git(repo, "config", "core.pager", "touch /tmp/pwned")
    assert gitops.review_diff(str(repo), []) is None


@pytest.mark.asyncio
async def test_the_reviewer_gets_the_diff_in_its_prompt(storage, repo):
    from ccc import gitops

    queue = storage.create_queue("calc", str(repo), "s2")  # legacy flags: may run commands
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    _git(repo, "commit", "-qam", "break it")
    head = gitops._git(str(repo), "rev-parse", "HEAD").stdout.strip()
    _task_run(storage, queue, "change add", head, "Changed add.")
    reviews.request(storage, queue.id)
    fake = FakeReviewer("VERDICT: FAIL — calc.py:2 subtracts")
    await reviews.tick(storage, fake, usage_fn=_no_usage)
    assert "+    return a - b" in fake.calls[0][1]
