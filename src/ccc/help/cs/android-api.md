# Aplikace pro Android a API

ccc má aplikaci pro Android (`android/` v repozitáři — jak ji sestavit
a nainstalovat: [android/README.md](../../../../android/README.md)).
S ccc mluví přes malé HTTP API: konverzace a jejich zprávy, odeslání
zprávy, schvalování nástrojů, nová konverzace, limity využití — a proud
změn, takže telefon novou odpověď nebo žádost o schválení uvidí hned.

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
3. `ccc api token` vytvoří token, kterým se aplikace přihlásí, a vypíše
   ho — **jen tentokrát**: ccc si drží jen jeho otisk (SHA-256), takže ho
   z databáze nikdo nepřečte. Je token pryč, nebo se ztratil telefon?
   `ccc api token --new` vytvoří nový; starý hned přestane platit, i pro
   otevřená spojení.
4. V aplikaci zadej adresu (stačí `<počítač>.<tailnet>.ts.net`) a token.

Bez služby ho spustí v terminálu `ccc api serve` (`--port` pro jiný
port).

## V aplikaci

Všechno, co umí okno ccc, upravené pro telefon: konverzace, fronta
úkolů, běhy a diffy, recenze, cíle, workflow, otázky, rutiny, živé
relace, analytika, nastavení — a Claude Code interaktivní konverzace
živě, s klávesami pro jeho nabídky.

**Oznámení** (Připojení → *Oznamovat, i když je aplikace zavřená*):
aplikace drží spojení s ccc otevřené i na pozadí a dá ti vědět
o schválení — odpovíš přímo v oznámení —, chybě, limitu využití nebo
hotové odpovědi. Žádný push server se nepoužívá; na Xiaomi / HyperOS
aplikaci povol běh na pozadí, jinak ji systém zastaví.

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
| `POST /conversations/{id}/archive` | `{"archived": true \| false}` — do [Archivu](archive.md) / zpět |
| `DELETE /conversations/{id}` | smazat ji z ccc (ne, když na ní Claude pracuje); přepis Claude Code zůstane |
| `POST /conversations/{id}/group` | `{"name": "…"}` do vlastní skupiny (vznikne, je-li nová), `null` ze skupiny ven |
| `GET /conversations/{id}/export` | `{"filename", "markdown"}` — konverzace jako Markdown, tajné údaje zamaskované |
| `GET /conversations/{id}/files?q=` | soubory její složky pro @zmínku, nejlepší první |
| `POST /conversations` | založit konverzaci: `{"path", "name", "options": [klíče], "interactive", "remote_control", "auto_continue", "worktree", "session_id", "pr", "prompt"}` — jako v [Zahájení konverzace](new-conversation.md); vynechané volby jsou výchozí |
| `GET /conversations/{id}/tasks` | její [fronta úkolů](tasks.md) a oba přepínače; `POST` přidá `{"text", "when"}` — when je prázdné (co nejdřív), `HH:MM`, `RRRR-MM-DD HH:MM` nebo `reset` |
| `POST /tasks/{id}` | `{"text"}` / `{"when"}` úkolu, který ještě nezačal; `DELETE` ho odebere; `POST /tasks/{id}/move` `{"delta": -1 \| 1}` |
| `POST /conversations/{id}/switches` | `{"paused": bool}` nespouštět další úkoly, `{"auto_continue": bool}` po limitu využití |
| `GET /conversations/{id}/runs` | její běhy, nejnovější první: stav, tokeny, [commit](git.md) |
| `GET /runs/{id}/diff` | commit běhu po řádcích (druh, soubor, čísla řádků, jde komentovat) |
| `POST /runs/{id}/comments` | `{"comments": [{"index", "text"}]}` k řádkům diffu, poslané Claudovi jako jeden úkol |
| `POST /runs/{id}/revert` | vrátí commit běhu novým commitem; `{"tell": true}` k tomu zařadí poznámku pro Clauda |
| `GET /conversations/{id}/reviews` | její [recenze](review.md), nejnovější první; `POST` o jednu požádá `{"instructions", "until_pass", "rounds"}`; `POST …/reviews/stop`; `POST /reviews/{id}/apply` pošle nálezy recenze FAIL / PARTIAL zpět jako úkol |
| `GET /conversations/{id}/goals` | její [smyčky k cíli](goal.md); `POST` jednu spustí `{"goal", "check", "rounds"}`; `POST …/goals/stop` |
| `GET /workflow-templates` | šablony [workflow](workflows.md) s jejich kroky |
| `GET /conversations/{id}/workflows` | její běhy workflow, každý s kroky a tím, co řekl každý agent; `POST` jeden spustí `{"template", "task", "check", "rounds"}`; `POST …/workflows/answer` `{"approve", "note"}` u schvalovacího kroku; `POST …/workflows/stop` |
| `GET /conversations/{id}/asks` | [otázky](asking.md) od ní a pro ni; `POST` se zeptá jiné `{"to", "question", "deliver"}`; `POST /asks/{id}/cancel` |
| `GET /routines` | všechny [rutiny](routines.md) a druhy plánu; `POST` přidá `{"conversation_id", "name", "prompt", "kind", "value", "fresh"}`; `POST /routines/{id}` ji změní, `DELETE` smaže; `POST …/enabled` `{"enabled"}`, `POST …/run` |
| `GET /live-sessions` | [relace Claude Code](live-sessions.md) běžící na počítači; `POST /live-sessions/{id}/prompt` `{"prompt"}` |
| `GET /analytics?year=&month=` | tokeny měsíce po dnech, modelech a konverzacích, měsíce s daty ([Analytika](analytics.md)); `POST /analytics/archive` archivuje skončené měsíce hned |
| `GET /settings` | [nastavení](settings.md) ccc s možnostmi u každého (tajné údaje jen jako nastaveno / nenastaveno); `POST` některá změní; `POST /settings/telegram-test`, `telegram-off`, `discord-test`, `discord-off` |
| `POST /prompt-presets` | `{"presets": [{"name", "text", "send_now"}]}` — všechny, v pořadí; `POST /launch-presets` uloží předvolbu nové konverzace, `POST /launch-presets/delete` `{"name"}` |
| `GET /conversations/{id}/terminal` | co teď ukazuje Claude Code interaktivní konverzace — obrazovka s barvami (ANSI) a kurzorem |
| `POST /conversations/{id}/terminal` | do jejího Claude Code: `{"paste", "submit"}` text jako jedno vložení (potom Enter, pokud `submit` není false), `{"keys": […]}` klávesy (Enter, Escape, Tab, BTab, šipky, Home, End, PageUp, PageDown, BSpace, Space, C-c, C-d, C-l, C-o, C-r, C-t, C-u), `{"type": "y"}` pár znaků |
| `POST /backup` | zálohovat databázi hned |
| `GET /launch-options` | volby, se kterými jde konverzace založit (klíče a popisky) |
| `GET /projects` | naposledy použité složky |
| `GET /sessions?path=` | relace Claude Code ve složce, nejnovější první (k pokračování: `session_id` v `POST /conversations` se `session_resume`) |
| `GET /launch-presets` | předvolby okna Nová konverzace a poslední volba |
| `GET /prompt-presets` | přednastavené prompty (Alt+1 … 9 v ccc) |
| `GET /groups` | seskupení a tvé vlastní skupiny; `POST /groups/rename` `{"old", "new"}`, `POST /groups/delete` `{"name"}` |
| `GET /search?q=` | hledání ve všech konverzacích (i archivovaných), nejnovější první |
| `GET /waiting` | konverzace, které tě potřebují, nejnaléhavější první (Alt+N v ccc) |
| `GET /permissions` | všechna čekající [schválení](approvals.md) |
| `POST /permissions/{id}` | `{"decision": "allow" \| "always" \| "deny"}` |
| `GET /usage` | [limity využití](limits.md) (null, když nejsou známé) |
| `GET /events` | Server-Sent Events: `changed` s `{"conversations": [id], "removed": [id]}`, kdykoli se nějaká změní |
