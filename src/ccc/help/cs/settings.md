# Nastavení a notifikace

`Ctrl+P` otevře Nastavení — všechno, co se dá změnit, v jednom okně.
Změň, co potřebuješ, a stiskni `Ctrl+S` (*Uložit*). `Esc` (*Zrušit*)
změny zahodí. Tlačítka jako *Poslat testovací zprávu*, *Vypnout* nebo
*Zálohovat hned* fungují okamžitě.

![Nastavení](../../../../docs/screenshots/settings.png)

## Sekce

| Sekce | |
|---|---|
| Vzhled | jazyk — *Automaticky* se řídí systémem (`LANG`), uložení jiného jazyka restartuje okno ccc; barevný motiv — mění se už při výběru, zůstane po Uložit |
| Notifikace přes Telegram | viz níže |
| Notifikace přes Discord | viz níže |
| Fronty | text *pokračuj* posílaný po limitu využití a rezerva využití — viz [Limity využití](limits.md) |
| Přednastavené prompty | tvé prompty na `Alt+1` … `Alt+9` — viz níže |
| Předvolby nové konverzace | smaže předvolby uložené v okně [Nová konverzace](new-conversation.md) |
| Exporty | složka pro exportované konverzace (`e`) a snímky obrazovky (`Alt+S`); volitelně posílat každý export na Telegram / Discord |
| Měsíční archiv analytiky | viz [Analytika](analytics.md) |
| Data | kde je databáze a její denní zálohy, *Zálohovat hned* |

Stejné hodnoty se dají nastavit i z příkazové řádky, viz
[Příkazová řádka](command-line.md).

## Přednastavené prompty

Prompty, které píšeš pořád dokola — „pokračuj“, „spusť testy a oprav, co
selže“, „zkontroluj tenhle soubor: “ — uložené jednou, použitelné
v každé konverzaci přes `Alt+1` … `Alt+9`.

- **Nastavení:** *Přednastavené prompty* → *Přidat* / *Upravit*:
  **název** (ukazuje se v liště), **prompt** a **Odeslat hned (s
  Enterem)**. *Nahoru* / *Dolů* určují pořadí — první je `Alt+1`.
  Nejvýš 9.
- **Použití:** stiskni klávesu, nebo klikni na předvolbu v liště.
  - Prompty `⏎` se hned **odešlou**.
  - Prompty `✎` se **vloží do pole pro zprávu** (nebo do vstupu Clauda),
    abys je dopsal(a), třeba přidal(a) název souboru.

![Editor přednastaveného promptu](../../../../docs/screenshots/prompt_preset.png)

## Notifikace přes Telegram

ccc ti napíše, když konverzace **dokončí frontu**, **zastaví se chybou**,
**potřebuje tě** (pauza na limitu, čekající schválení nástroje) nebo
**narazí na limit využití** a později **pokračuje**.

1. V Telegramu založ bota přes [@BotFather](https://t.me/BotFather)
   (`/newbot`) a zkopíruj jeho token.
2. Pošli botovi libovolnou zprávu, pak v prohlížeči otevři
   `https://api.telegram.org/bot<TOKEN>/getUpdates` a zkopíruj číslo za
   `"chat":{"id":`.
3. Obojí vyplň v Nastavení, stiskni *Poslat testovací zprávu* a pak
   *Uložit*.

## Notifikace přes Discord

Stejné zprávy můžou chodit do kanálu na Discordu — místo Telegramu,
nebo k němu.

1. V Discordu: nastavení kanálu → *Integrace* → *Webhooky* → *Nový
   webhook* → *Kopírovat URL webhooku*.
2. Vlož ji v Nastavení, stiskni *Poslat testovací zprávu* a pak
   *Uložit*.

URL nikomu nedávej: kdo ji má, může do kanálu psát. Tokeny a webhooky
se ukládají v databázi ccc, zobrazují se zamaskované a nikdy se
nelogují.

## Zálohy

Daemon každý den zálohuje databázi ccc a drží posledních 14
(`~/.local/share/ccc/backups/`). Jak zálohu obnovit, viz
[Řešení potíží](troubleshooting.md).
