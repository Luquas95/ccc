"""Multi-agent workflows: a conversation's task goes through a chain of
specialists — a planner, your approval, the coder (the conversation), a
check, independent reviewers in parallel, an arbiter — with bounded
rounds back to the coder when the work doesn't pass.

A workflow template is a list of steps (JSON, see validate()):

- plan     a read-only agent writes the plan and its acceptance criteria;
- gate     waits for you to approve (or reject) what came before;
- code     the task goes into the conversation's queue (with the plan,
           and in later rounds what the reviewers found);
- check    a command, e.g. `pytest -q` (only where Claude may run commands);
- review   1–4 reviewers in parallel, each with its own brief and model;
- arbiter  compares the reviewers' findings, checks what they disagree
           on and gives the verdict.

A failed check, review (without an arbiter after it) or arbiter sends the
work back to the last code step — one more round, up to the run's limit.
Every agent other than the coder only reads (the reviewer's sandbox,
ccc.reviews.command): ccc hands them the diff.

Built-in templates are in BUILT_IN; your own are kept in the database
(import / export as JSON). The daemon advances the runs (tick())."""
from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ccc import gitops, goals, i18n, reviews
from ccc.i18n import N_, _
from ccc.limits import exhausted_until
from ccc.notify import CAT_ATTENTION, CAT_RESULTS
from ccc.models import (
    ItemStatus, PromptRun, Queue, Review, RunStatus, Verdict, WorkflowRun, WorkflowStatus,
)

KINDS = ("plan", "gate", "code", "check", "review", "arbiter")
MAX_REVIEWERS = 4
MAX_ROUNDS = 10
EXPORT_SUFFIX = ".ccc-workflow.json"
_MODEL = re.compile(r"^[A-Za-z0-9._\[\]-]{1,60}$")
FINISHED = (WorkflowStatus.PASSED, WorkflowStatus.FAILED, WorkflowStatus.STOPPED, WorkflowStatus.ERROR)

_CORRECTNESS = ("Check that the change does what the task asks: bugs, wrong edge cases, missing or weak tests, "
                "callers of changed code that now break.")
_SECURITY = ("Check security and robustness only: input validation, injection, secrets, permissions, error "
             "handling, resource leaks. Ignore style.")
BUILT_IN: dict[str, dict] = {
    "plan-build-review": {
        "title": N_("Plan → approve → build → review"),
        "max_rounds": 3,
        "steps": [
            {"type": "plan", "model": "opus"},
            {"type": "gate", "text": N_("Approve the plan?")},
            {"type": "code"},
            {"type": "check"},
            {"type": "review", "reviewers": [{"name": "correctness", "brief": _CORRECTNESS}]},
        ],
    },
    "build-reviews-arbiter": {
        "title": N_("Build → two reviews in parallel → arbiter"),
        "max_rounds": 3,
        "steps": [
            {"type": "code"},
            {"type": "check"},
            {"type": "review", "reviewers": [
                {"name": "correctness", "brief": _CORRECTNESS},
                {"name": "security", "brief": _SECURITY, "model": "opus"},
            ]},
            {"type": "arbiter", "model": "opus"},
        ],
    },
    "full": {
        "title": N_("Plan → approve → build → two reviews → arbiter"),
        "max_rounds": 3,
        "steps": [
            {"type": "plan", "model": "opus"},
            {"type": "gate", "text": N_("Approve the plan?")},
            {"type": "code"},
            {"type": "check"},
            {"type": "review", "reviewers": [
                {"name": "correctness", "brief": _CORRECTNESS},
                {"name": "security", "brief": _SECURITY, "model": "opus"},
            ]},
            {"type": "arbiter", "model": "opus"},
        ],
    },
}
KIND_LABELS = {"plan": N_("plan"), "gate": N_("your approval"), "code": N_("build"), "check": N_("check"),
               "review": N_("review"), "arbiter": N_("arbiter")}


# --- templates ------------------------------------------------------------------


def validate(definition: dict) -> dict:
    """A clean copy of a template definition, or ValueError saying what's
    wrong with it."""
    if not isinstance(definition, dict) or not isinstance(definition.get("steps"), list) or not definition["steps"]:
        raise ValueError(_("A workflow needs a list of steps."))
    steps = []
    for n, raw in enumerate(definition["steps"], start=1):
        if not isinstance(raw, dict) or raw.get("type") not in KINDS:
            raise ValueError(_("Step {n}: the type must be one of {kinds}.").format(n=n, kinds=", ".join(KINDS)))
        step = {"type": raw["type"]}
        for key in ("brief", "text", "command"):
            if raw.get(key) is not None:
                step[key] = _text(raw[key], n, key)
        if raw.get("model") is not None:
            step["model"] = _model(raw["model"], n)
        if step["type"] == "review":
            reviewers = raw.get("reviewers")
            if not isinstance(reviewers, list) or not 1 <= len(reviewers) <= MAX_REVIEWERS:
                raise ValueError(_("Step {n}: a review has 1 to {max} reviewers.").format(n=n, max=MAX_REVIEWERS))
            step["reviewers"] = []
            for reviewer in reviewers:
                if not isinstance(reviewer, dict) or not isinstance(reviewer.get("brief", ""), str):
                    raise ValueError(_("Step {n}: each reviewer needs a brief.").format(n=n))
                clean = {"name": _text(str(reviewer.get("name") or f"reviewer {len(step['reviewers']) + 1}")[:40],
                                       n, "name"),
                         "brief": _text(reviewer.get("brief", ""), n, "brief")}
                if reviewer.get("model") is not None:
                    clean["model"] = _model(reviewer["model"], n)
                step["reviewers"].append(clean)
        if step["type"] == "arbiter" and (not steps or steps[-1]["type"] != "review"):
            raise ValueError(_("Step {n}: an arbiter comes right after a review.").format(n=n))
        if step["type"] in ("check", "review", "arbiter") and not any(s["type"] == "code" for s in steps):
            raise ValueError(_("Step {n}: there's no build (code) step before it to check.").format(n=n))
        steps.append(step)
    rounds = definition.get("max_rounds", 3)
    if not isinstance(rounds, int) or not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError(_("max_rounds must be a whole number from 1 to {max}.").format(max=MAX_ROUNDS))
    clean = {"max_rounds": rounds, "steps": steps}
    if isinstance(definition.get("title"), str):
        clean["title"] = _text(definition["title"], 0, "title")
    return clean


def _text(value, n: int, key: str) -> str:
    """A template's text without anything that could fake what `ccc
    workflow import` shows before you say --yes: no control characters
    (ESC, \\r) and no invisible / direction-changing Unicode. A command is
    one line of printable ASCII — what you read is what runs."""
    if not isinstance(value, str):
        raise ValueError(_("Step {n}: {key} must be text.").format(n=n, key=key))
    if key == "command":
        if not all(32 <= ord(c) < 127 for c in value):
            raise ValueError(_("Step {n}: a command is one line of plain ASCII characters.").format(n=n))
        return value
    if any(c not in "\n\t" and unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Co", "Cs") for c in value):
        raise ValueError(_("Step {n}: {key} has control characters.").format(n=n, key=key))
    return value


def _model(value, n: int) -> str:
    if not isinstance(value, str) or not _MODEL.match(value):
        raise ValueError(_("Step {n}: “{model}” isn't a model name.").format(n=n, model=value))
    return value


def templates(storage) -> dict[str, dict]:
    """Every template by name: the built-in ones, then yours."""
    return {**BUILT_IN, **storage.workflow_templates()}


def title(name: str, definition: dict) -> str:
    return _(definition["title"]) if name in BUILT_IN else definition.get("title") or name


def describe(definition: dict) -> str:
    """The template's graph in one line: plan → your approval → build → …
    A check command the template brings is shown — it would run."""
    parts = []
    for step in definition["steps"]:
        label = _(KIND_LABELS[step["type"]])
        if step["type"] == "review":
            label += f" ×{len(step['reviewers'])}"
        if step["type"] == "check" and step.get("command"):
            label += f" {step['command']!r}"
        parts.append(label)
    return " → ".join(parts) + "  " + _("(back to build at most {n}×)").format(n=definition.get("max_rounds", 3))


def details(definition: dict) -> str:
    """Everything a template would put in front of the agents or run — its
    briefs, gate texts and commands — to read before importing it."""
    lines = []
    for n, step in enumerate(definition["steps"], start=1):
        lines.append(f"{n}. {step['type']}" + (f" (model {step['model']})" if step.get("model") else ""))
        for key in ("brief", "text"):
            if step.get(key):
                lines.append(f"   {key}: {step[key]}")
        if step.get("command"):
            lines.append("   " + _("command (runs in the project folder): {command}").format(command=repr(step["command"])))
        for reviewer in step.get("reviewers", []):
            lines.append(f"   - {reviewer['name']}" + (f" (model {reviewer['model']})" if reviewer.get("model") else "")
                         + f": {reviewer['brief']}")
    return "\n".join(lines)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(_("Can't read {path}: {error}").format(path=path, error=error.strerror or error)) from error
    except ValueError as error:
        raise ValueError(_("{path} isn't JSON.").format(path=path)) from error


def read_template(path: str | Path) -> tuple[dict, dict]:
    """A template file read once: (its data — pass it to import_template —,
    the validated template to show before importing it)."""
    data = _read_json(Path(path).expanduser())
    return data, validate(data)


def import_template(storage, path: str | Path, name: str | None = None, data: dict | None = None) -> str:
    """Save a template from a JSON file (ValueError when it isn't one).
    `ccc workflow import` reads it once, shows details() and passes the
    same `data` here after --yes — the file can't change in between."""
    path = Path(path).expanduser()
    data = _read_json(path) if data is None else data
    name = (name or (data.get("name") if isinstance(data, dict) else None) or path.name.removesuffix(EXPORT_SUFFIX)
            .removesuffix(".json")).strip()
    if not name or name in BUILT_IN:
        raise ValueError(_("Pick a name that isn't one of the built-in templates."))
    storage.save_workflow_template(name, validate(data))
    return name


def export_template(storage, name: str, folder: str | Path) -> Path:
    found = templates(storage)
    if name not in found:
        raise ValueError(_("No workflow template “{name}”.").format(name=name))
    definition = dict(found[name], name=name)
    if name in BUILT_IN:
        definition["title"] = _(definition["title"])
    path = Path(folder).expanduser() / f"{name}{EXPORT_SUFFIX}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(definition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# --- runs -------------------------------------------------------------------------


def active(storage, queue_id: int) -> WorkflowRun | None:
    for run in storage.list_workflow_runs(queue_id):
        if run.status not in FINISHED:
            return run
    return None


def start(storage, queue_id: int, name: str, task: str, check_command: str = "",
          max_rounds: int | None = None) -> WorkflowRun:
    if not task.strip():
        raise ValueError(_("Describe the task the workflow works on."))
    if storage.find_queue(queue_id) is None:
        raise ValueError(_("That conversation doesn't exist."))
    found = templates(storage)
    if name not in found:
        raise ValueError(_("No workflow template “{name}”.").format(name=name))
    if active(storage, queue_id) is not None:
        raise ValueError(_("A workflow is already running in this conversation."))
    if goals.active(storage, queue_id) is not None or reviews.active(storage, queue_id) is not None:
        raise ValueError(_("A goal or a review is already running in this conversation."))
    definition = validate(found[name])
    rounds = max(1, min(int(max_rounds or definition["max_rounds"]), MAX_ROUNDS))
    return storage.add_workflow_run(queue_id, name, definition, task.strip(), check_command.strip(), rounds,
                                    storage.last_run_id(queue_id))


def _finish(storage, run: WorkflowRun, status: WorkflowStatus, reason: str, notifier=None) -> WorkflowRun:
    storage.update_workflow_run(run.id, status=status, last_reason=reason, finished_at=datetime.now())
    run = storage.get_workflow_run(run.id)
    if notifier is not None and status != WorkflowStatus.STOPPED:
        queue = storage.find_queue(run.queue_id)
        icon = {WorkflowStatus.PASSED: "✅", WorkflowStatus.FAILED: "⛔", WorkflowStatus.ERROR: "✖"}[status]
        notifier.notify(_("{icon} {name}: workflow “{workflow}” {status} — {reason}").format(
            icon=icon, name=queue.name if queue else "?", workflow=run.name, status=_(STATUS_LABELS[status]),
            reason=reason[:300]), CAT_RESULTS)
    return run


STATUS_LABELS = {
    WorkflowStatus.RUNNING: N_("running"),
    WorkflowStatus.WAITING: N_("waits for you"),
    WorkflowStatus.PASSED: N_("passed"),
    WorkflowStatus.FAILED: N_("failed"),
    WorkflowStatus.STOPPED: N_("stopped"),
    WorkflowStatus.ERROR: N_("error"),
}


def stop(storage, queue_id: int) -> bool:
    run = active(storage, queue_id)
    if run is None:
        return False
    item = storage.get_item(run.item_id) if run.item_id else None
    if item is not None and item.status == ItemStatus.PENDING:
        storage.skip_item(item.id)
    _finish(storage, run, WorkflowStatus.STOPPED, _("stopped by you"))
    return True


def answer_gate(storage, queue_id: int, approve: bool, note: str = "") -> bool:
    """Your answer at a gate: on to the next step, or the run fails."""
    run = active(storage, queue_id)
    if run is None or run.status != WorkflowStatus.WAITING:
        return False
    storage.add_workflow_event(run.id, run.step, run.round, "gate", _("your answer"), "done",
                               "APPROVED" if approve else "REJECTED", note.strip())
    if not approve:
        _finish(storage, run, WorkflowStatus.FAILED, _("rejected at the gate") + (f": {note.strip()}" if note else ""))
        return True
    findings = run.findings + (f"\n\n{_('Your note:')} {note.strip()}" if note.strip() else "")
    storage.update_workflow_run(run.id, status=WorkflowStatus.RUNNING, step=run.step + 1, findings=findings.strip())
    return True


# --- the steps ----------------------------------------------------------------------


def _language_line() -> str:
    return "\nWrite your answer in Czech; keep the VERDICT line's keyword in English." if i18n.language() == "cs" else ""


def plan_prompt(run: WorkflowRun, step: dict) -> str:
    return ("You are the planner of a team of agents. Read the code — don't change any file. Write a concrete plan "
            "for the task below: which files change and how, in what order, the risks, and the acceptance criteria "
            "the finished work will be judged by. Another agent implements it; reviewers check it against your "
            f"criteria.\n\nThe task:\n{run.task}"
            + (f"\n\nYour brief:\n{step['brief']}" if step.get("brief") else "") + _language_line().replace(
                "; keep the VERDICT line's keyword in English", ""))


def code_prompt(run: WorkflowRun, step: dict) -> str:
    text = _("Implement this task:\n\n{task}").format(task=run.task)
    if step.get("brief"):
        # The template's author wrote this, not the user: marked as such.
        text += "\n\n" + _("Notes from the workflow template “{name}” (a style guide, not new tasks):\n{brief}").format(
            name=run.name, brief="\n".join(f"> {line}" for line in step["brief"].splitlines()))
    if run.plan:
        text += "\n\n" + _("The approved plan:\n\n{plan}").format(plan=run.plan)
    if run.round > 1 and run.findings:
        text += "\n\n" + _("Round {n} of {max}. The last check / review found:\n\n{findings}\n\nFix that.").format(
            n=run.round, max=run.max_rounds, findings=run.findings)
    return text


def reviewer_prompt(run: WorkflowRun, reviewer: dict, what: str) -> str:
    plan = f"\n\nThe plan it followed (with the acceptance criteria):\n{run.plan}" if run.plan else ""
    return ("You are one of several independent reviewers of changes another agent made in this repository. Judge "
            "the code as it is now; don't change any file.\n\n"
            f"The task:\n{run.task}{plan}\n\nYour brief — check this, not everything:\n"
            f"{reviewer.get('brief') or 'Check that the change is correct.'}\n\nWhat to review:\n{what}\n\n"
            "Be concrete: file:line and what is wrong. End with exactly one line, one of:\n"
            "VERDICT: PASS — what you verified\nVERDICT: FAIL — file:line, what is wrong\n"
            "VERDICT: PARTIAL — what you could not verify and why" + _language_line())


def arbiter_prompt(run: WorkflowRun, step: dict, reports: str, what: str) -> str:
    plan = f"\n\nThe plan (with the acceptance criteria):\n{run.plan}" if run.plan else ""
    return ("You are the arbiter. Independent reviewers checked changes another agent made in this repository. "
            "Compare their findings, check in the code what they disagree on or might have missed, and decide "
            "whether the work is done. Don't change any file.\n\n"
            f"The task:\n{run.task}{plan}\n\nThe reviewers' reports:\n{reports}\n\nWhat changed:\n{what}"
            + (f"\n\nYour brief:\n{step['brief']}" if step.get("brief") else "")
            + "\n\nList what must still be fixed (file:line, what), then end with exactly one line, one of:\n"
            "VERDICT: PASS — why it's done\nVERDICT: FAIL — what must still be fixed\n"
            "VERDICT: PARTIAL — what could not be verified" + _language_line())


def _record(storage, queue: Queue, run: WorkflowRun, label: str, result) -> None:
    """Count a one-shot agent's tokens like a task's (Analytics, queue detail)."""
    run_id = storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue.id, queue_item_id=None, prompt_text=f"🧩 {run.name}: {label}",
        started_at=datetime.now(), finished_at=datetime.now(), status=result.status, cost_usd=result.cost_usd,
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens, cache_creation_tokens=result.cache_creation_tokens,
        duration_ms=result.duration_ms, num_turns=result.num_turns, result_text=result.result_text,
        error_text=result.error_text, workflow_run_id=run.id,
    ))
    for model_name, tokens in result.model_usage.items():
        storage.insert_run_model_usage(run_id, model_name, **tokens)


async def _limit_wait(storage, usage_fn) -> bool:
    """True when a usage window (or your reserve) is used up: wait."""
    from ccc.orchestrator import usage_reserve
    from ccc.usage_api import get_pro_usage

    usage = await asyncio.to_thread(usage_fn or get_pro_usage)
    reserve = usage_reserve(storage)
    return exhausted_until(usage, datetime.now(), threshold=reserve or 100) is not None


async def _agent(storage, queue: Queue, run: WorkflowRun, step_index: int, kind: str, name: str, prompt: str,
                 model: str | None, run_fn) -> tuple[bool, str, Verdict | None, str]:
    """Run one read-only agent: (ok, its output, verdict, the verdict's reason)."""
    event = storage.add_workflow_event(run.id, step_index, run.round, kind, name)
    result = await run_fn(queue.project_path, prompt, model or reviews.model_for(storage, queue))
    _record(storage, queue, run, f"{_(KIND_LABELS[kind])} — {name}", result)
    output = (result.result_text or "").strip()
    if result.status != RunStatus.SUCCESS:
        storage.update_workflow_event(event, "error", output=(result.error_text or "")[:4000])
        return False, result.error_text or "", None, ""
    verdict, reason = reviews.parse_verdict(output)
    storage.update_workflow_event(event, "done", verdict.value if verdict else "", output)
    return True, output, verdict, reason


def _what(storage, queue: Queue, run: WorkflowRun) -> tuple[str, str] | None:
    """(label, what to review — with the diff) of the work since the run began."""
    found = reviews.scope(storage, queue, Review(id=0, queue_id=queue.id, base_run_id=run.base_run_id))
    return (found[0], found[1]) if found else None


def _back_to_code(storage, run: WorkflowRun, findings: str, reason: str, notifier) -> WorkflowRun:
    """The work didn't pass: one more round from the last code step before here."""
    code_steps = [n for n, s in enumerate(run.template["steps"][:run.step]) if s["type"] == "code"]
    if not code_steps:
        return _finish(storage, run, WorkflowStatus.FAILED, reason, notifier)
    if run.round >= run.max_rounds:
        return _finish(storage, run, WorkflowStatus.FAILED, _("out of rounds: {reason}").format(reason=reason),
                       notifier)
    storage.update_workflow_run(run.id, round=run.round + 1, step=code_steps[-1], findings=findings.strip(),
                                last_reason=reason, item_id=None)
    return storage.get_workflow_run(run.id)


async def step_once(storage, run: WorkflowRun, run_fn=reviews.execute, notifier=None, usage_fn: Callable = None,
                    check_fn=goals.run_check) -> bool:
    """Do what the run's current step can do now. True when it moved on
    (the next step may go at once), False when it waits."""
    queue = storage.find_queue(run.queue_id)
    if queue is None:
        _finish(storage, run, WorkflowStatus.ERROR, _("the conversation was deleted"))
        return False
    steps = run.template["steps"]
    if run.step >= len(steps):
        _finish(storage, run, WorkflowStatus.PASSED, run.last_reason or _("every step passed"), notifier)
        return False
    step = steps[run.step]
    kind = step["type"]

    if kind == "gate":
        if run.status != WorkflowStatus.WAITING:
            storage.update_workflow_run(run.id, status=WorkflowStatus.WAITING)
            storage.add_workflow_event(run.id, run.step, run.round, "gate", _(step.get("text") or "Approve?"), "waiting")
            if notifier is not None:
                notifier.notify(_("⏸ {name}: the workflow “{workflow}” waits for your approval (w).").format(
                    name=queue.name, workflow=run.name), CAT_ATTENTION)
        return False

    if kind == "code":
        item = storage.get_item(run.item_id) if run.item_id else None
        if item is None:
            item = storage.add_queue_item(queue.id, code_prompt(run, step), model=step.get("model"))
            storage.update_workflow_run(run.id, item_id=item.id)
            storage.add_workflow_event(run.id, run.step, run.round, "code", _("task in the conversation"), "running",
                                       output=item.prompt_text)
            return False
        if item.status in (ItemStatus.FAILED, ItemStatus.SKIPPED):
            _finish(storage, run, WorkflowStatus.ERROR, _("its task failed or was removed: {error}").format(
                error=queue.last_error or "?"), notifier)
            return False
        if item.status != ItemStatus.DONE or not await asyncio.to_thread(reviews.ready, storage, queue):
            return False
        storage.update_workflow_run(run.id, step=run.step + 1, item_id=None)
        return True

    if kind == "check":
        # Yours first; a template's own command was shown before it was imported.
        command = run.check_command or step.get("command")
        if not command or not gitops.claude_can_run_commands(queue):
            storage.update_workflow_run(run.id, step=run.step + 1)
            return True
        event = storage.add_workflow_event(run.id, run.step, run.round, "check", command)
        passed, output = await asyncio.to_thread(check_fn, command, queue.project_path)
        storage.update_workflow_event(event, "done", "PASS" if passed else "FAIL", output)
        if not passed:
            reason = _("The check `{command}` failed").format(command=command)
            _back_to_code(storage, run, f"{reason}:\n{output}", reason, notifier)
            return True
        storage.update_workflow_run(run.id, step=run.step + 1)
        return True

    # plan / review / arbiter: read-only agents — mind the usage limits.
    if await _limit_wait(storage, usage_fn):
        return False

    if kind == "plan":
        ok, output, _verdict, _reason = await _agent(storage, queue, run, run.step, "plan", _("planner"),
                                                     plan_prompt(run, step), step.get("model"), run_fn)
        if not ok:
            _finish(storage, run, WorkflowStatus.ERROR, _("the planner failed: {error}").format(error=output[:200]),
                    notifier)
            return False
        storage.update_workflow_run(run.id, step=run.step + 1, plan=output)
        return True

    what = _what(storage, queue, run)
    if what is None:
        reason = _("Nothing changed — there's nothing to review.")
        _back_to_code(storage, run, reason, reason, notifier)
        return True
    label, text = what

    if kind == "review":
        results = await asyncio.gather(*[
            _agent(storage, queue, run, run.step, "review", r["name"], reviewer_prompt(run, r, text), r.get("model"),
                   run_fn) for r in step["reviewers"]])
        if not all(ok for ok, *_rest in results):
            _finish(storage, run, WorkflowStatus.ERROR, _("a reviewer failed"), notifier)
            return False
        reports = "\n\n".join(f"### {r['name']} — {v.value if v else '?'}\n{out}"
                              for r, (_ok, out, v, _reason) in zip(step["reviewers"], results))
        nxt = steps[run.step + 1]["type"] if run.step + 1 < len(steps) else None
        if nxt == "arbiter":
            storage.update_workflow_run(run.id, step=run.step + 1, findings=reports)
            return True
        failing = [(r, v, reason) for r, (_ok, _out, v, reason) in zip(step["reviewers"], results) if v != Verdict.PASS]
        if failing:
            reason = "; ".join(f"{r['name']}: {v.value if v else '?'} {why}".strip() for r, v, why in failing)
            _back_to_code(storage, run, reports, reason, notifier)
            return True
        storage.update_workflow_run(run.id, step=run.step + 1, last_reason=_("reviews passed"))
        return True

    # arbiter
    ok, output, verdict, reason = await _agent(storage, queue, run, run.step, "arbiter", _("arbiter"),
                                               arbiter_prompt(run, step, run.findings, text), step.get("model"), run_fn)
    if not ok or verdict is None:
        _finish(storage, run, WorkflowStatus.ERROR, _("the arbiter gave no verdict"), notifier)
        return False
    if verdict != Verdict.PASS:
        _back_to_code(storage, run, output, f"{verdict.value}: {reason}", notifier)
        return True
    storage.update_workflow_run(run.id, step=run.step + 1, last_reason=reason)
    return True


async def advance(storage, run: WorkflowRun, run_fn=reviews.execute, notifier=None, usage_fn: Callable = None,
                  check_fn=goals.run_check) -> WorkflowRun:
    """Move a run on as far as it can go now."""
    while True:
        run = storage.get_workflow_run(run.id)
        if run.status in FINISHED or run.status == WorkflowStatus.WAITING:
            return run
        if not await step_once(storage, run, run_fn, notifier, usage_fn, check_fn):
            return storage.get_workflow_run(run.id)


_working: dict[int, asyncio.Task] = {}


async def tick(storage, notifier=None) -> None:
    """Advance every running workflow, each in its own task so a long
    review in one doesn't hold up the others."""
    for run_id, task in list(_working.items()):
        if task.done():
            del _working[run_id]
            if not task.cancelled() and task.exception() is not None:
                raise task.exception()
    for run in storage.list_workflow_runs():
        if run.status == WorkflowStatus.RUNNING and run.id not in _working:
            _working[run.id] = asyncio.create_task(advance(storage, run, notifier=notifier))
