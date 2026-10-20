# Příkazová řádka

Všechno, co ccc umí, je dostupné z TUI; pár věcí jde i z shellu — třeba
ve skriptech nebo přes SSH. Příkazy jsou ve virtualenvu checkoutu
(`~/ccc/.venv/bin/`); přidej si ho do `PATH`, nebo je volej celou cestou.
Výpisy příkazů jsou v jazyce ccc. Zkratky změněné přes `ccc keys` se do
běžícího ccc dostanou po jeho restartu (`systemctl --user restart
ccc-tui`); změněné v Nastavení platí hned.

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
| `ccc keys list` | všechny [klávesové zkratky](settings.md#klávesové-zkratky): id akce, klávesa (`*` = změněná), co dělá |
| `ccc keys check KLÁVESA [AKCE]` | je klávesa volná? (kdo ji má, nebo proč nejde použít); s id akce: volná pro tu akci — při kolizi návratový kód 1 |
| `ccc keys set AKCE KLÁVESA` | dá akci novou klávesu — při kolizi odmítne (návratový kód 1) |
| `ccc keys reset [AKCE]` | zpět na výchozí klávesu (jedna akce, nebo všechny) |
| `ccc keys export SLOŽKA` | zapíše zkratky do `SLOŽKA/ccc-keys.json` |
| `ccc keys import CESTA` | použije zkratky ze souboru `ccc-keys.json` (nebo ze složky s ním) — při kolizi nenaimportuje nic |
| `ccc-daemon` | samotný daemon (normálně ho spouští `ccc.service`) |
