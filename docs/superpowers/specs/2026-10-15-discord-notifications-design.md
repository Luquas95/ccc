# Discord notifikace — návrh

Datum: 2026-10-15. Schváleno uživatelem („Ano. Udělej to.“) podle návrhu v konverzaci.

## Cíl

Stejné notifikace jako Telegram (fronta hotová, potřebuje tě, chyba, limit / pokračuje)
i do Discordu. Kanály jsou nezávislé: jen Telegram, jen Discord, nebo oba.

## Mechanismus

- Discord **webhook** kanálu (Integrations → Webhooks → New Webhook → Copy URL).
  `POST <url>` s JSON `{"content": text}`; žádný bot ani chat id.
- `send_discord(url, text)` v `src/ccc/notify.py` přes `urllib`, text oříznutý na
  2000 znaků (limit Discordu), hlavička `User-Agent` (Discord/Cloudflare odmítá
  výchozí `Python-urllib`), `allowed_mentions: {"parse": []}` — text z Clauda
  nesmí pingnout `@everyone`.
- Uloženo v `settings` pod `discord_webhook`. URL je tajná (kdo ji zná, píše do
  kanálu): v UI skrytá, v CLI maskovaná, nikdy v logu ani v textu výjimky.
- Přijímá se jen `https://discord.com/api/webhooks/…` (a `discordapp.com`,
  `ptb.`, `canary.`) — `is_discord_webhook(url)`.

## Notifier

- `configured()` = aspoň jeden kanál nastaven. `send_now` pošle do všech
  nastavených kanálů, vrací True, když aspoň jeden uspěl. Chyba kanálu se
  zaloguje jen typem výjimky („Discord notification failed (HTTPError)“).
- Konstruktor: `sender` (Telegram, beze změny), nově `discord_sender`.

## Rozhraní

- Settings: sekce *Discord notifications* pod Telegramem — stav, pole Webhook
  URL (password, prázdné = ponechat uloženou), návod, *Send test message*
  (s hodnotou z formuláře), *Turn off*; neplatná URL → hláška u testu, Save ji
  odmítne s notifikací.
- CLI: `ccc config discord-webhook [URL]` (bez hodnoty maskovaně),
  `ccc config discord-test`.
- README: sekce Discord, tabulka příkazů, Settings; screenshot Settings.

## Testy

`tests/test_notify.py` (send_discord request, oba kanály, jeden selže, URL se
nezaloguje, validace URL), `tests/test_cli.py` (discord-webhook/test),
`tests/test_tui_settings.py` (uložení, ponechání, test zprávy, turn off,
neplatná URL).
