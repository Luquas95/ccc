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
| Fronty | text *pokračuj* posílaný po limitu využití a rezerva využití — viz [Limity využití](limits.md); model [recenzenta](review.md) |
| Přednastavené prompty | tvé prompty na `Alt+1` … `Alt+9` — viz níže |
| Předvolby nové konverzace | smaže předvolby uložené v okně [Nová konverzace](new-conversation.md) |
| Klávesové zkratky | změna libovolné klávesy, export / import — viz níže |
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

## Klávesové zkratky

Každou klávesu v ccc jde změnit: *Klávesové zkratky* → *Upravit
zkratky…* otevře okno se všemi akcemi a jejich klávesami (změněné jsou
žlutě).

- **Změna:** vyber akci, pak *Stisknout klávesu* a stiskni novou klávesu
  (jakoukoli — i Esc nebo Ctrl+P), nebo napiš její název (`Ctrl+O`,
  `Alt+S`, `F5`, `+`) a *Nastavit*. *Výchozí* vrátí jednu, *Vše výchozí*
  všechny.
- **Nejdřív kontrola:** klávesa, která koliduje, se odmítne a okno řekne
  proč — nikdy se neuloží. Kolize je:
  - jiná akce na stejné klávese tam, kde fungují obě zároveň (např. dva
    pohledy, nebo pohled a klávesa, která funguje všude),
  - klávesa, kterou terminál nerozliší (Ctrl+I je Tab, Ctrl+M je Enter,
    Ctrl+H je Backspace), Ctrl+C, Ctrl+B (prefix tmuxu) nebo
    Ctrl+Shift+C / V (kopírovat / vložit),
  - klávesa, kterou potřebují seznamy a textová pole (šipky, Enter, Tab,
    mezerník, editační klávesy jako Ctrl+A / E / K / U / W),
  - u kláves, které fungují i z panelu Claude Code (přepnutí, zavření
    Claude, přednastavené prompty, Nastavení, snímek obrazovky, zavření
    ccc): klávesa Claude Code (Ctrl+T, Ctrl+O, Ctrl+R, Alt+P, …) nebo
    klávesa bez Ctrl / Alt (F-klávesy jsou v pořádku) — do Claude Code by
    už nešla napsat.
- **Uložit** (`Ctrl+S`) a nové klávesy platí hned — ukazuje je menu,
  tlačítka i `?`. Toto okno ukládá samo, nezávisle na Uložit v Nastavení.
- **Export / Import:** napiš složku (předvyplněná je složka exportů) —
  *Exportovat* do ní zapíše `ccc-keys.json`, *Importovat* ho z ní načte
  (nebo ze souboru, který zadáš) a zkontroluje stejně: jediná kolize a
  nenaimportuje se nic. Soubor přenes na jiný počítač a máš tam své
  klávesy.

Totéž z příkazové řádky: `ccc keys` (viz [Příkazová řádka](command-line.md)).
Ostatní stránky příručky uvádějí výchozí klávesy.

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

## Tajemství se maskují

Co z ccc odchází — každá zpráva na Telegram / Discord a každá exportovaná
konverzace (`e`) — má tajemství nejdřív nahrazená za `[redacted]`: API
klíče a tokeny známého tvaru (`sk-ant-…`, `ghp_…`, `AKIA…`, Slack, Stripe,
JWT, bloky soukromých klíčů…), hesla v URL, hlavičky `Bearer …` a hodnoty
pojmenované jako tajemství (`DB_PASSWORD=…`, `"client_secret": …`).
Rozpoznatelný začátek zůstane, takže z `ANTHROPIC_API_KEY=sk-ant-[redacted]`
pořád poznáš, co tam bylo. Je to pojistka, ne záruka: tajemství bez
známého tvaru a bez výmluvného názvu projde. Snímky obrazovky (`Alt+S`)
jsou obrázky obrazovky a nemaskují se.

## Zálohy

Daemon každý den zálohuje databázi ccc a drží posledních 14
(`~/.local/share/ccc/backups/`). Jak zálohu obnovit, viz
[Řešení potíží](troubleshooting.md).
