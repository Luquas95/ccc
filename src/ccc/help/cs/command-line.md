# Příkazová řádka

Všechno, co ccc umí, je dostupné z TUI; pár věcí jde i z shellu — třeba
ve skriptech nebo přes SSH. Příkazy jsou ve virtualenvu checkoutu
(`~/ccc/.venv/bin/`); přidej si ho do `PATH`, nebo je volej celou cestou.
Výpisy příkazů jsou v jazyce ccc.

| Příkaz | |
|---|---|
| `ccc` | otevře ccc |
| `ccc add <složka> "<prompt>"` | zařadí prompt do konverzace té složky (běží na pozadí) |
| `ccc backup` | hned zazálohuje databázi |
| `ccc archive-analytics` | hned zapíše skončené měsíce do [měsíčního archivu analytiky](analytics.md) |
| `ccc config analytics-folder [CESTA\|off]` | ukáže / nastaví / vypne složku měsíčního archivu |
| `ccc config continue-text ["…"]` | ukáže / nastaví zprávu pro pokračování posílanou po limitu využití |
| `ccc config usage-reserve [N\|off]` | ukáže / nastaví [rezervu využití](limits.md) |
| `ccc config language [auto\|en\|cs]` | ukáže / nastaví jazyk ccc (auto = podle systému) |
| `ccc config telegram-token [TOKEN]` | ukáže (zamaskovaný) / nastaví token Telegram bota |
| `ccc config telegram-chat [ID]` | ukáže / nastaví ID Telegram chatu |
| `ccc config telegram-test` | pošle testovací zprávu na Telegram |
| `ccc config discord-webhook [URL\|off]` | ukáže (zamaskovaný) / nastaví / odebere webhook Discordu |
| `ccc config discord-test` | pošle testovací zprávu na Discord |
| `ccc-daemon` | samotný daemon (normálně ho spouští `ccc.service`) |
