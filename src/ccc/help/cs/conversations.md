# Konverzace

V Konverzacích (`c`) pracuješ s Claudem. Vlevo je seznam tvých
konverzací, vpravo ta vybraná. V seznamu se pohybuješ `↑` `↓` — pravá
strana se hned přepne.

![Konverzace](../../../../docs/screenshots/conversations.png)

## Seznam

Každá konverzace má před názvem značku a za ním `·N`, když v její
[frontě](tasks.md) čeká N úkolů:

| Značka | Význam |
|---|---|
| `●` | Claude pracuje |
| `‖` | čeká na obnovení limitu využití, nebo je pozastavená |
| `✖` | zastavila se chybou — potřebuje tě |
| `?` | Claude čeká, až [schválíš nástroj](approvals.md) |
| `◆` | nová odpověď, kterou jsi ještě neviděl(a) |

Když nemáš žádnou konverzaci, stojí vpravo **BEZ KONVERZACE** — stiskni
`n` a nějakou založ.

## Claude Code vedle ccc

Konverzace založená přes `n` spouští **skutečné Claude Code** — totéž,
jako když v terminálu napíšeš `claude`, se vším všudy: lomítkové příkazy,
schvalování nástrojů, `Shift+Tab`, `Esc Esc`, historie, obrázky. ccc ho
ukazuje vpravo od svého menu:

| Klávesa | |
|---|---|
| `Enter` na konverzaci | otevře její Claude Code a přepne tam klávesnici |
| `Alt+0` | přepíná klávesnici mezi ccc a Claudem (nebo klikni, kam chceš psát) |
| `Ctrl+]` | zavře panel s Claudem — Claude běží dál, `Enter` ho zase otevře |
| výběr myší | zkopíruje do schránky (i přes SSH a v Termuxu) |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | zkopíruje výběr / vloží poslední kopii |

Pod Claudem je lišta s tvými [přednastavenými prompty](settings.md) —
kliknutím prompt použiješ. `Alt+0` a `Ctrl+]` jsou i v liště ccc dole.

Dobré vědět:

- Claude běží dál, když přepneš na jinou konverzaci nebo obrazovku,
  zavřeš ccc (`Ctrl+Q`) nebo zavřeš panel. Daemon ho drží naživu na
  pozadí, a když spadne, spustí ho znovu i s historií.
- Úkoly z [fronty](tasks.md) se do Clauda vloží, kdykoli je nečinný —
  jako bys je napsal(a) sám/sama.
- V úzkém okně (pod 100 sloupců, třeba telefon) zabere Claude celé okno;
  `Alt+0` tě vrátí do ccc.
- Každá taková konverzace drží v paměti proces Claude Code — ty hotové
  [archivuj](archive.md) (`x`).

## Konverzace na pozadí

Konverzace, které sdílejí složku, mají řádek ⚠: jejich úkoly na pozadí
se střídají, viz [Git](git.md#více-konverzací-v-jedné-složce).

Prompty zařazené přes `+` (Živé relace, detail fronty) nebo `ccc add`
běží **na pozadí** (headless): daemon pro každý úkol spustí `claude -p`
bez terminálu. U nich ukazuje přepis sám ccc:

- Odpovědi Clauda se vykreslují jako Markdown; použití nástroje je
  sbalený řádek `▸ ⚙ Tool: …` — `Enter` nebo kliknutí ukáže jeho vstup
  a výsledek.
- **Pole pro zprávu** pod přepisem přidá zprávu na konec fronty: `Enter`
  odešle, `Ctrl+J` začne nový řádek. `Alt+1` … `Alt+9` odešlou nebo
  vloží [přednastavený prompt](settings.md).
- Řádek nad polem říká, co se děje: *Připraveno*, *Další úkol v 23:00*,
  *Čeká na obnovení limitu do 14:30*,
  *✖ Zablokováno: … — stiskni r pro nový pokus*, …
- Běh na pozadí se nemůže zastavit a zeptat se tě na schválení nástroje,
  proto se jeho režim oprávnění volí předem — viz
  [Schvalování nástrojů](approvals.md).

## Záhlaví

Nahoře je název konverzace, složka projektu a volby Claude Code, jestli
je zapnuté automatické pokračování a u konverzace se
[vzdáleným ovládáním](remote-control.md) odkaz pro telefon.

## Další klávesy

| Klávesa | |
|---|---|
| `t` | [fronta úkolů](tasks.md) této konverzace |
| `r` | zastavená chybou: znovu spustí selhaný úkol; pozastavená na limitu: pokračuje — viz [Limity využití](limits.md) |
| `p` | [schválí nástroj](approvals.md), na který Claude čeká |
| `x` | [archivuje](archive.md) konverzaci |
| `/` | hledá ve všech konverzacích (i archivovaných); `Enter` na výsledku ho otevře |
| `e` | exportuje konverzaci jako Markdown (do `conversations/` ve složce pro exporty, viz [Nastavení](settings.md)) |
| `n` | [založí novou konverzaci](new-conversation.md) |
