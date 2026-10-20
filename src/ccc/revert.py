"""Undo a run: revert the commit ccc made for one of a conversation's
tasks (queue detail → u, `ccc revert`). It's a new commit, so it can be
undone in turn; nothing is rewritten.

Like ccc's other git (see gitops), only in conversations where Claude may
run commands anyway, and only while the conversation does nothing — a
task working on the files would mix its edits into the revert."""
from __future__ import annotations

from ccc import gitops, reviews
from ccc.i18n import _
from ccc.models import PromptRun


class RevertError(ValueError):
    """Why a run can't be reverted (a message for the user)."""


def check(storage, run: PromptRun) -> None:
    """RevertError when the run can't be reverted now."""
    if not run.git_commit:
        raise RevertError(_("This run made no commit — there's nothing to revert."))
    if run.reverted_by:
        raise RevertError(_("This run was already reverted ({commit}).").format(commit=run.reverted_by[:7]))
    queue = storage.find_queue(run.queue_id)
    if queue is None:
        raise RevertError(_("That conversation doesn't exist."))
    if not gitops.claude_can_run_commands(queue):
        raise RevertError(_("ccc runs git only in conversations started with “Skip all permission checks”."))
    if not reviews.ready(storage, queue):
        raise RevertError(_("The conversation is working — revert once it's idle."))


def revert(storage, run: PromptRun) -> str:
    """Revert the run's commit; the revert commit. RevertError otherwise."""
    check(storage, run)
    queue = storage.get_queue(run.queue_id)
    outcome = gitops.revert_commit(queue.project_path, run.git_commit, queue.name)
    if outcome.commit is None:
        raise RevertError(outcome.note)
    storage.set_run_reverted(run.id, outcome.commit)
    return outcome.commit


def tell_claude(storage, run: PromptRun, revert_commit: str):
    """Queue a short note so Claude knows the files changed under it."""
    task = (run.prompt_text.strip().splitlines() or [""])[0][:200]
    return storage.add_queue_item(run.queue_id, _(
        "Note: the changes of your task “{task}” were reverted (commit {commit} undoes {original}). The files are "
        "back as they were before it. Take them as they are now and don't redo that work unless I ask. Just "
        "acknowledge in one line.").format(task=task, commit=revert_commit[:7], original=run.git_commit[:7]))
