# Android app & API

ccc has an Android app (`android/` in the repository — how to build and
install it: [android/README.md](../../../android/README.md)). It talks
to ccc over a small HTTP API: the conversations and their messages,
sending a message, approving tool calls, starting a conversation, usage
limits — and a stream of changes, so the phone sees a new reply or an
approval right away.

Like the TUI, the API only reads and writes ccc's database; the daemon
does the work. It's reachable only from your
[Tailscale](https://tailscale.com) network, and every request needs a
token.

## Turning it on

1. Install its service: `bin/install.sh --api` (with the other options
   you use). The API then runs as `ccc-api.service` and listens on
   `127.0.0.1:8737` — on this computer only.
2. Put it on your tailnet with HTTPS: `tailscale serve --bg 8737`. It's
   then at `https://<computer>.<tailnet>.ts.net/api/v1/` — `tailscale
   serve status` prints the address.
3. `ccc api token` makes the token the app signs in with and prints it
   — **only this once**: ccc keeps just its fingerprint (SHA-256), so
   nobody can read it from the database. Lost it, or lost the phone?
   `ccc api token --new` makes a new one; the old one stops working at
   once, open connections too.
4. In the app enter the address (just `<computer>.<tailnet>.ts.net`
   will do) and the token.

Without the service, `ccc api serve` runs it in the terminal
(`--port` for another port).

## Endpoints

Every path starts with `/api/v1`; every request has the header
`Authorization: Bearer <token>`. Answers are JSON; an error is
`{"error": "…"}` in ccc's language.

| | |
|---|---|
| `GET /status` | the daemon running?, how many conversations, running, waiting for approval |
| `GET /conversations` | the list in the TUI's order, with groups, states, queued messages and markers; `?archived=1` the archive |
| `GET /conversations/{id}` | one, with its queued messages and approvals waiting |
| `GET /conversations/{id}/messages` | its transcript, each message with an `index`; `?after=N` only newer ones, `?before=N` older ones, `?limit=` how many (200) |
| `POST /conversations/{id}/messages` | `{"text": "…"}` queues a message, as the message box does |
| `POST /conversations/{id}/retry` | retry / resume a blocked or paused conversation (`r`) |
| `POST /conversations/{id}/seen` | mark it read |
| `POST /conversations/{id}/archive` | `{"archived": true \| false}` — into the [Archive](archive.md) / back |
| `DELETE /conversations/{id}` | delete it from ccc (not while Claude works on it); Claude Code's transcript stays |
| `POST /conversations/{id}/group` | `{"name": "…"}` into an own group (made if new), `null` out of it |
| `GET /conversations/{id}/export` | `{"filename", "markdown"}` — the conversation as Markdown, secrets masked |
| `GET /conversations/{id}/files?q=` | files of its folder for an @-mention, best first |
| `POST /conversations` | start one: `{"path", "name", "options": [keys], "interactive", "remote_control", "auto_continue", "worktree", "session_id", "pr", "prompt"}` — as in [Starting a conversation](new-conversation.md); options left out are the defaults |
| `GET /conversations/{id}/tasks` | its [task queue](tasks.md) and the two switches; `POST` adds `{"text", "when"}` — when is empty (as soon as possible), `HH:MM`, `YYYY-MM-DD HH:MM` or `reset` |
| `POST /tasks/{id}` | `{"text"}` / `{"when"}` of a task that hasn't started; `DELETE` removes it; `POST /tasks/{id}/move` `{"delta": -1 \| 1}` |
| `POST /conversations/{id}/switches` | `{"paused": bool}` start no further tasks, `{"auto_continue": bool}` after a usage limit |
| `GET /conversations/{id}/runs` | its runs, newest first: state, tokens, the [commit](git.md) |
| `GET /runs/{id}/diff` | the run's commit line by line (kind, file, line numbers, commentable) |
| `POST /runs/{id}/comments` | `{"comments": [{"index", "text"}]}` on lines of the diff, sent to Claude as one task |
| `POST /runs/{id}/revert` | undo the run's commit with a new one; `{"tell": true}` also queues a note for Claude |
| `GET /conversations/{id}/reviews` | its [reviews](review.md), newest first; `POST` asks for one `{"instructions", "until_pass", "rounds"}`; `POST …/reviews/stop`; `POST /reviews/{id}/apply` sends a FAIL / PARTIAL review's findings back as a task |
| `GET /conversations/{id}/goals` | its [goal loops](goal.md); `POST` starts one `{"goal", "check", "rounds"}`; `POST …/goals/stop` |
| `GET /workflow-templates` | the [workflow](workflows.md) templates with their steps |
| `GET /conversations/{id}/workflows` | its workflow runs, each with its steps and what every agent said; `POST` starts one `{"template", "task", "check", "rounds"}`; `POST …/workflows/answer` `{"approve", "note"}` at a gate; `POST …/workflows/stop` |
| `GET /conversations/{id}/asks` | [questions](asking.md) to and from it; `POST` asks another `{"to", "question", "deliver"}`; `POST /asks/{id}/cancel` |
| `GET /routines` | every [routine](routines.md) and the schedule kinds; `POST` adds one `{"conversation_id", "name", "prompt", "kind", "value", "fresh"}`; `POST /routines/{id}` changes it, `DELETE` removes it; `POST …/enabled` `{"enabled"}`, `POST …/run` |
| `GET /live-sessions` | [Claude Code sessions](live-sessions.md) running on the computer; `POST /live-sessions/{id}/prompt` `{"prompt"}` |
| `GET /analytics?year=&month=` | a month's tokens per day, model and conversation, the months there are ([Analytics](analytics.md)); `POST /analytics/archive` archives finished months now |
| `GET /settings` | ccc's [settings](settings.md) with the choices for each (secrets only as set / not set); `POST` changes some of them; `POST /settings/telegram-test`, `telegram-off`, `discord-test`, `discord-off` |
| `POST /prompt-presets` | `{"presets": [{"name", "text", "send_now"}]}` — all of them, in order; `POST /launch-presets` saves a New conversation preset, `POST /launch-presets/delete` `{"name"}` |
| `POST /backup` | back the database up now |
| `GET /launch-options` | the options a conversation can be started with (keys and labels) |
| `GET /projects` | recently used folders |
| `GET /sessions?path=` | Claude Code sessions recorded in a folder, newest first (to resume one: `session_id` in `POST /conversations` with `session_resume`) |
| `GET /launch-presets` | the New conversation presets and the last choice |
| `GET /prompt-presets` | the preset prompts (Alt+1 … 9 in ccc) |
| `GET /groups` | the grouping and your own groups; `POST /groups/rename` `{"old", "new"}`, `POST /groups/delete` `{"name"}` |
| `GET /search?q=` | search every conversation (archived too), newest first |
| `GET /waiting` | conversations that need you, most urgent first (Alt+N in ccc) |
| `GET /permissions` | every [approval](approvals.md) waiting |
| `POST /permissions/{id}` | `{"decision": "allow" \| "always" \| "deny"}` |
| `GET /usage` | the [usage limits](limits.md) (null when unknown) |
| `GET /events` | Server-Sent Events: `changed` with `{"conversations": [ids], "removed": [ids]}` whenever one changes |
