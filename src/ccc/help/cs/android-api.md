# Aplikace pro Android a API

Pro ccc vzniká aplikace pro Android (`android/` v repozitáři). S ccc
mluví přes malé HTTP API, které už můžeš zapnout: konverzace a jejich
zprávy, odeslání zprávy, schvalování nástrojů, nová konverzace, limity
využití — a proud změn, takže telefon novou odpověď nebo žádost
o schválení uvidí hned.

API stejně jako TUI jen čte a zapisuje databázi ccc; práci dělá daemon.
Je dostupné jen z tvé sítě [Tailscale](https://tailscale.com) a každý
požadavek potřebuje token.

## Zapnutí

1. Nainstaluj jeho službu: `bin/install.sh --api` (s ostatními volbami,
   které používáš). API pak běží jako `ccc-api.service` a poslouchá na
   `127.0.0.1:8737` — jen na tomto počítači.
2. Vystav ho do tailnetu s HTTPS: `tailscale serve --bg 8737`. Pak je na
   `https://<počítač>.<tailnet>.ts.net/api/v1/` — adresu vypíše
   `tailscale serve status`.
3. `ccc api token` vypíše token, kterým se aplikace přihlásí.
   `ccc api token --new` vytvoří nový; starý hned přestane platit
   (třeba při ztrátě telefonu) — restartuj API
   (`systemctl --user restart ccc-api`).

Bez služby ho spustí v terminálu `ccc api serve` (`--port` pro jiný
port).

## Endpointy

Každá cesta začíná `/api/v1`; každý požadavek má hlavičku
`Authorization: Bearer <token>`. Odpovědi jsou JSON; chyba je
`{"error": "…"}` v jazyce ccc.

| | |
|---|---|
| `GET /status` | běží daemon?, kolik konverzací, kolik běží, kolik čeká na schválení |
| `GET /conversations` | seznam v pořadí jako v TUI, se skupinami, stavy, zprávami ve frontě a značkami; `?archived=1` archiv |
| `GET /conversations/{id}` | jedna konverzace s jejími zprávami ve frontě a čekajícími schváleními |
| `GET /conversations/{id}/messages` | její přepis, každá zpráva s `index`; `?after=N` jen novější, `?before=N` starší, `?limit=` kolik (200) |
| `POST /conversations/{id}/messages` | `{"text": "…"}` zařadí zprávu do fronty, jako pole pro zprávu |
| `POST /conversations/{id}/retry` | zopakovat / obnovit zablokovanou nebo pozastavenou konverzaci (`r`) |
| `POST /conversations/{id}/seen` | označit jako přečtenou |
| `POST /conversations` | založit konverzaci: `{"path", "name", "options": [klíče], "interactive", "remote_control", "auto_continue", "worktree", "session_id", "pr", "prompt"}` — jako v [Zahájení konverzace](new-conversation.md); vynechané volby jsou výchozí |
| `GET /launch-options` | volby, se kterými jde konverzace založit (klíče a popisky) |
| `GET /projects` | naposledy použité složky |
| `GET /permissions` | všechna čekající [schválení](approvals.md) |
| `POST /permissions/{id}` | `{"decision": "allow" \| "always" \| "deny"}` |
| `GET /usage` | [limity využití](limits.md) (null, když nejsou známé) |
| `GET /events` | Server-Sent Events: `changed` s `{"conversations": [id], "removed": [id]}`, kdykoli se nějaká změní |
