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
| `POST /conversations` | start one: `{"path", "name", "options": [keys], "interactive", "remote_control", "auto_continue", "worktree", "session_id", "pr", "prompt"}` — as in [Starting a conversation](new-conversation.md); options left out are the defaults |
| `GET /launch-options` | the options a conversation can be started with (keys and labels) |
| `GET /projects` | recently used folders |
| `GET /permissions` | every [approval](approvals.md) waiting |
| `POST /permissions/{id}` | `{"decision": "allow" \| "always" \| "deny"}` |
| `GET /usage` | the [usage limits](limits.md) (null when unknown) |
| `GET /events` | Server-Sent Events: `changed` with `{"conversations": [ids], "removed": [ids]}` whenever one changes |
