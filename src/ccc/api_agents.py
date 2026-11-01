"""The agents part of ccc's HTTP API (see ccc.api): reviews (v in the
TUI), goal loops (g) and workflows (w). The same functions as the TUI's windows; the daemon runs them.

GET  /api/v1/conversations/{id}/reviews      its reviews, newest first; POST {"instructions", "until_pass", "rounds"}
POST /api/v1/conversations/{id}/reviews/stop
POST /api/v1/reviews/{id}/apply              send a FAIL / PARTIAL review's findings back as a task
GET  /api/v1/conversations/{id}/goals        its goals; POST {"goal", "check", "rounds"}; POST …/goals/stop
GET  /api/v1/workflow-templates              the templates with their steps
GET  /api/v1/conversations/{id}/workflows    its runs with their steps; POST {"template", "task", "check", "rounds"}
POST /api/v1/conversations/{id}/workflows/answer  {"approve": bool, "note"} at a gate; POST …/workflows/stop
"""
from __future__ import annotations

from http import HTTPStatus

from ccc import goals, reviews, workflows
from ccc.api_common import ApiError, iso, route, text_of
from ccc.i18n import _
from ccc.models import Verdict, WorkflowStatus

STEP_DONE, STEP_NOW, STEP_WAITS, STEP_TO_COME = "done", "now", "waits", "to_come"


def _rounds(body: dict, default: int | None) -> int | None:
    value = body.get("rounds")
    if value is None or value == "":
        return default
    if not isinstance(value, int) or isinstance(value, bool):
        raise ApiError(HTTPStatus.BAD_REQUEST, _("rounds must be a number."))
    return value


def _flag(body: dict, key: str, default: bool) -> bool:
    value = body.get(key, default)
    if not isinstance(value, bool):
        raise ApiError(HTTPStatus.BAD_REQUEST, _("{name} must be true or false.").format(name=key))
    return value


def _started(start, *args, **kwargs):
    """Run a domain start / request: its ValueError is a message for the user."""
    try:
        return start(*args, **kwargs)
    except ValueError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, str(exc)) from exc


class AgentEndpoints:
    storage: object

    def _agent_routes(self) -> list:
        ok = route
        return [
            ok(r"/conversations/(\d+)/reviews", lambda ids, q, b: self.reviews(*ids)),
            ok(r"/conversations/(\d+)/reviews", lambda ids, q, b: self.request_review(*ids, b), "POST",
               HTTPStatus.CREATED),
            ok(r"/conversations/(\d+)/reviews/stop", lambda ids, q, b: self.stop_review(*ids), "POST"),
            ok(r"/reviews/(\d+)/apply", lambda ids, q, b: self.apply_review(*ids), "POST"),
            ok(r"/conversations/(\d+)/goals", lambda ids, q, b: self.goals(*ids)),
            ok(r"/conversations/(\d+)/goals", lambda ids, q, b: self.start_goal(*ids, b), "POST", HTTPStatus.CREATED),
            ok(r"/conversations/(\d+)/goals/stop", lambda ids, q, b: self.stop_goal(*ids), "POST"),
            ok(r"/workflow-templates", lambda ids, q, b: self.workflow_templates()),
            ok(r"/conversations/(\d+)/workflows", lambda ids, q, b: self.workflows(*ids)),
            ok(r"/conversations/(\d+)/workflows", lambda ids, q, b: self.start_workflow(*ids, b), "POST",
               HTTPStatus.CREATED),
            ok(r"/conversations/(\d+)/workflows/answer", lambda ids, q, b: self.answer_workflow(*ids, b), "POST"),
            ok(r"/conversations/(\d+)/workflows/stop", lambda ids, q, b: self.stop_workflow(*ids), "POST"),
        ]

    # --- reviews -------------------------------------------------------------------

    def reviews(self, queue_id: int) -> dict:
        """The conversation's reviews, newest first, and whether one waits or runs."""
        self._queue(queue_id)
        return {
            "active": reviews.active(self.storage, queue_id) is not None,
            "reviews": [
                {
                    "id": r.id,
                    "status": r.status.value,
                    "status_label": _(reviews.STATUS_LABELS[r.status]),
                    "verdict": r.verdict.value if r.verdict else None,
                    "round": r.round,
                    "max_rounds": r.max_rounds,
                    "until_pass": r.until_pass,
                    "scope": r.scope,
                    "instructions": r.instructions,
                    "report": r.report,
                    "error": r.error,
                    "fix_sent": r.fix_item_id is not None,
                    "can_apply": r.verdict in (Verdict.FAIL, Verdict.PARTIAL) and r.fix_item_id is None,
                    "not_before": iso(r.not_before),
                    "created_at": iso(r.created_at),
                    "finished_at": iso(r.finished_at),
                }
                for r in self.storage.list_reviews(queue_id)
            ],
        }

    def request_review(self, queue_id: int, body: dict) -> dict:
        """{"instructions", "until_pass", "rounds"}: it starts once the conversation is idle."""
        self._queue(queue_id)
        _started(reviews.request, self.storage, queue_id, text_of(body, "instructions"),
                 _flag(body, "until_pass", False), _rounds(body, reviews.DEFAULT_ROUNDS))
        return self.reviews(queue_id)

    def stop_review(self, queue_id: int) -> dict:
        self._queue(queue_id)
        reviews.stop(self.storage, queue_id)
        return self.reviews(queue_id)

    def apply_review(self, review_id: int) -> dict:
        review = self.storage.find_review(review_id)
        if review is None:
            raise ApiError(HTTPStatus.NOT_FOUND, _("No such review."))
        if review.verdict not in (Verdict.FAIL, Verdict.PARTIAL) or review.fix_item_id is not None:
            raise ApiError(HTTPStatus.CONFLICT, _("This review has no findings to send."))
        reviews.apply(self.storage, review)
        return self.reviews(review.queue_id)

    # --- goal loops -------------------------------------------------------------------

    def goals(self, queue_id: int) -> dict:
        self._queue(queue_id)
        return {
            "active": goals.active(self.storage, queue_id) is not None,
            "goals": [
                {
                    "id": g.id,
                    "goal": g.goal,
                    "check_command": g.check_command,
                    "round": g.round,
                    "max_rounds": g.max_rounds,
                    "status": g.status.value,
                    "status_label": _(goals.STATUS_LABELS[g.status]),
                    "phase_label": _(goals.PHASE_LABELS[g.phase]).format(n=g.round),
                    "last_reason": g.last_reason,
                    "created_at": iso(g.created_at),
                    "finished_at": iso(g.finished_at),
                }
                for g in self.storage.list_goals(queue_id)
            ],
        }

    def start_goal(self, queue_id: int, body: dict) -> dict:
        """{"goal", "check", "rounds"}: rounds of work, the check command and a review until it's met."""
        self._queue(queue_id)
        _started(goals.start, self.storage, queue_id, text_of(body, "goal"), text_of(body, "check"),
                 _rounds(body, goals.DEFAULT_ROUNDS))
        return self.goals(queue_id)

    def stop_goal(self, queue_id: int) -> dict:
        self._queue(queue_id)
        goals.stop(self.storage, queue_id)
        return self.goals(queue_id)

    # --- workflows ------------------------------------------------------------------------

    def workflow_templates(self) -> list[dict]:
        """Every template: built-in ones, then yours (with everything they say and run)."""
        found = []
        for name, definition in workflows.templates(self.storage).items():
            clean = workflows.validate(definition)
            found.append({
                "name": name,
                "title": workflows.title(name, clean),
                "steps": workflows.describe(clean),
                "details": "" if name in workflows.BUILT_IN else workflows.details(clean),
                "max_rounds": clean.get("max_rounds", 3),
            })
        return found

    def workflows(self, queue_id: int) -> dict:
        self._queue(queue_id)
        active = workflows.active(self.storage, queue_id)
        return {
            "active": active is not None,
            "waiting": active is not None and active.status == WorkflowStatus.WAITING,
            "runs": [self._workflow_run(run) for run in self.storage.list_workflow_runs(queue_id)],
        }

    def _workflow_run(self, run) -> dict:
        steps = []
        for n, step in enumerate(run.template["steps"]):
            label = _(workflows.KIND_LABELS[step["type"]])
            if step["type"] == "review":
                label += f" ×{len(step['reviewers'])}"
            if n < run.step or run.status == WorkflowStatus.PASSED:
                state = STEP_DONE
            elif n == run.step and run.status == WorkflowStatus.WAITING:
                state = STEP_WAITS
            elif n == run.step and run.status == WorkflowStatus.RUNNING:
                state = STEP_NOW
            else:
                state = STEP_TO_COME
            steps.append({"label": label, "state": state})
        return {
            "id": run.id,
            "name": run.name,
            "task": run.task,
            "round": run.round,
            "max_rounds": run.max_rounds,
            "status": run.status.value,
            "status_label": _(workflows.STATUS_LABELS[run.status]),
            "last_reason": run.last_reason,
            "steps": steps,
            "events": [
                {"kind": e.kind, "kind_label": _(workflows.KIND_LABELS.get(e.kind, e.kind)), "name": e.name,
                 "round": e.round, "status": e.status, "verdict": e.verdict, "output": e.output,
                 "created_at": iso(e.created_at)}
                for e in reversed(self.storage.workflow_events(run.id))
            ],
            "created_at": iso(run.created_at),
        }

    def start_workflow(self, queue_id: int, body: dict) -> dict:
        """{"template", "task", "check", "rounds"} (rounds: empty = the template's)."""
        self._queue(queue_id)
        name = text_of(body, "template")
        if name not in workflows.templates(self.storage):
            raise ApiError(HTTPStatus.BAD_REQUEST, _("No such workflow template."))
        _started(workflows.start, self.storage, queue_id, name, text_of(body, "task"), text_of(body, "check"),
                 _rounds(body, None))
        return self.workflows(queue_id)

    def answer_workflow(self, queue_id: int, body: dict) -> dict:
        """{"approve": bool, "note"}: your answer at the step the run waits at."""
        self._queue(queue_id)
        if not workflows.answer_gate(self.storage, queue_id, _flag(body, "approve", False), text_of(body, "note")):
            raise ApiError(HTTPStatus.CONFLICT, _("No workflow waits for your answer."))
        return self.workflows(queue_id)

    def stop_workflow(self, queue_id: int) -> dict:
        self._queue(queue_id)
        workflows.stop(self.storage, queue_id)
        return self.workflows(queue_id)
