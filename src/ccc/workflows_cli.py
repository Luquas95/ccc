"""`ccc workflow …` — multi-agent workflows from the shell: templates
(list, import / export JSON, delete), runs (start, list, show), and the
answers a run waits for (approve, reject, stop). With --wait the exit
code says how it ended: 0 passed, 1 anything else."""
from __future__ import annotations

import argparse
import time

from ccc import workflows
from ccc.i18n import _
from ccc.models import WorkflowStatus
from ccc.routines_cli import conversation_id

WAIT_POLL_SECONDS = 5.0


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("workflow", help=_("Multi-agent workflows: plan, build, reviews, arbiter"))
    sub = parser.add_subparsers(dest="workflow_command", required=True)
    sub.add_parser("templates", help=_("The workflow templates and their steps"))
    imp = sub.add_parser("import", help=_("Show a workflow template from a JSON file; save it with --yes"))
    imp.add_argument("path")
    imp.add_argument("--name", default=None)
    imp.add_argument("--yes", action="store_true",
                     help=_("save it — after reading what it tells the agents and what it runs"))
    exp = sub.add_parser("export", help=_("Write a template to FOLDER/<name>.ccc-workflow.json"))
    exp.add_argument("template")
    exp.add_argument("folder")
    delete = sub.add_parser("delete", help=_("Delete one of your templates"))
    delete.add_argument("template")
    start = sub.add_parser("start", help=_("Run a workflow on a task in a conversation (the daemon runs it)"))
    start.add_argument("conversation", help=_("the conversation: its id or name"))
    start.add_argument("template")
    start.add_argument("task")
    start.add_argument("--check", default="", help=_("the command of its check step, e.g. \"pytest -q\""))
    start.add_argument("--rounds", type=int, default=None, help=_("at most this many rounds back to the build"))
    start.add_argument("--wait", action="store_true", help=_("wait until it ends; exit code 0 when it passed"))
    listing = sub.add_parser("list", help=_("Workflow runs, newest first"))
    listing.add_argument("conversation", nargs="?", default=None)
    show = sub.add_parser("show", help=_("A run's steps and what each agent said"))
    show.add_argument("run", type=int)
    for name, text in (("approve", _("Approve the step the run waits at")),
                       ("reject", _("Reject it: the run stops")), ("stop", _("Stop the conversation's workflow"))):
        command = sub.add_parser(name, help=text)
        command.add_argument("conversation")
        if name != "stop":
            command.add_argument("--note", default="", help=_("a note for the next step"))


def _line(run) -> str:
    return (f"{run.id:>4}  {run.created_at:%Y-%m-%d %H:%M}  {run.name:<22}  {run.round}/{run.max_rounds}  "
            f"{_(workflows.STATUS_LABELS[run.status]):<14}  {run.task.splitlines()[0][:50]}")


def wait(storage, run_id: int, sleep=time.sleep) -> int:
    told = False
    while True:
        run = storage.get_workflow_run(run_id)
        if run.status in workflows.FINISHED:
            print(_line(run))
            if run.last_reason:
                print(run.last_reason)
            return 0 if run.status == WorkflowStatus.PASSED else 1
        if run.status == WorkflowStatus.WAITING and not told:
            print(_("Waits for your answer: ccc workflow approve|reject {conversation}").format(
                conversation=run.queue_id))
            told = True
        sleep(WAIT_POLL_SECONDS)


def run(storage, args: argparse.Namespace, sleep=time.sleep) -> int:
    command = args.workflow_command
    try:
        if command == "templates":
            for name, definition in workflows.templates(storage).items():
                built_in = "" if name not in workflows.BUILT_IN else "  " + _("(built-in)")
                print(f"{name}{built_in} — {workflows.title(name, definition)}")
                print(f"    {workflows.describe(workflows.validate(definition))}")
            return 0
        if command == "import":
            definition = workflows.read_template(args.path)
            print(workflows.describe(definition))
            print(workflows.details(definition))
            if not args.yes:
                print(_("Not saved. A template tells the agents what to do (and a check command runs in the project) "
                        "— read the above; save it with --yes."))
                return 1
            name = workflows.import_template(storage, args.path, args.name)
            print(_("Template “{name}” saved.").format(name=name))
            return 0
        if command == "export":
            print(_("Exported to {path}").format(path=workflows.export_template(storage, args.template, args.folder)))
            return 0
        if command == "delete":
            if args.template in workflows.BUILT_IN or args.template not in storage.workflow_templates():
                raise ValueError(_("No template of yours called “{name}”.").format(name=args.template))
            storage.delete_workflow_template(args.template)
            print(_("Template “{name}” deleted.").format(name=args.template))
            return 0
        if command == "start":
            started = workflows.start(storage, conversation_id(storage, args.conversation), args.template, args.task,
                                      args.check, args.rounds)
            print(_("Workflow {id} started — the daemon runs its steps.").format(id=started.id))
            return wait(storage, started.id, sleep) if args.wait else 0
        if command == "list":
            queue_id = conversation_id(storage, args.conversation, include_archived=True) if args.conversation else None
            items = storage.list_workflow_runs(queue_id)
            for item in items:
                print(_line(item))
            if not items:
                print(_("No workflows yet."))
            return 0
        if command == "show":
            found = storage.find_workflow_run(args.run)
            if found is None:
                raise ValueError(_("No workflow run {id}.").format(id=args.run))
            print(_line(found))
            print(workflows.describe(found.template))
            for event in storage.workflow_events(found.id):
                print(f"\n## {workflows.KIND_LABELS.get(event.kind, event.kind)} · {event.name} "
                      f"(round {event.round}) {event.verdict or event.status}")
                if event.output:
                    print(event.output)
            return 0
        queue_id = conversation_id(storage, args.conversation, include_archived=True)
        if command in ("approve", "reject"):
            if not workflows.answer_gate(storage, queue_id, command == "approve", args.note):
                raise ValueError(_("No workflow waits for an answer there."))
            print(_("Approved — the workflow goes on.") if command == "approve" else _("Rejected — the workflow stops."))
            return 0
        if command == "stop":
            print(_("Workflow stopped.") if workflows.stop(storage, queue_id) else _("No workflow runs there."))
            return 0
    except ValueError as error:
        print(error)
        return 1
    return 2
