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

Za názvem je, jak moc je zaplněné kontextové okno konverzace, např.
`62%` — od prahu varování žlutě, od poplachu červeně (viz
*Zaplnění kontextu* níže).

Když nemáš žádnou konverzaci, stojí vpravo **BEZ KONVERZACE** — stiskni
`n` a nějakou založ.

## Filtr seznamu

Při desítkách konverzací otevře `f` nad seznamem filtr. Píšeš a seznam
se zúží na konverzace, jejichž **název nebo složka** obsahuje napsaný
text — bez ohledu na velikost písmen a diakritiku (`prilis` najde
*Příliš*); víc slov musí sedět všechna.

Značky na začátku filtrují podle **stavu** — každá jako samostatné slovo,
kombinovat je jde s textem (`? api`, `!? api`, `x`):

| Značka | Ukáže |
|---|---|
| `!` | Claude pracuje |
| `?` | čeká na tvoje schválení |
| `x` | zastavila se chybou |
| `*` | nová odpověď, kterou jsi ještě neviděl(a) |

Víc značek ukáže kterýkoli z těch stavů. `Enter` otevře první výsledek,
`Esc` filtr zruší. Dokud platí, je vidět v titulku seznamu
(`Fronty · filtr: api`); když nic nesedí, stojí v seznamu *Nic
neodpovídá*. Filtr vydrží obnovování seznamu, dokud ho nezrušíš nebo
neodejdeš z pohledu; konverzace, kterou z něj otevřeš, v seznamu zůstane,
i když přestane odpovídat (`*` přestane být nová, jakmile se na ni
podíváš). Klávesu změníš v Nastavení → Klávesové zkratky. Stejně to
funguje i v [Archivu](archive.md).

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
| `Alt+N` | otevře tady v panelu další konverzaci, která tě potřebuje (i z Claude Code) |
| výběr myší | zkopíruje do schránky (i přes SSH a v Termuxu) |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | zkopíruje výběr / vloží poslední kopii |

Pod Claudem je lišta s tvými [přednastavenými prompty](settings.md) —
kliknutím prompt použiješ. `Alt+0` a `Ctrl+]` jsou i v liště ccc dole.

**Co tě potřebuje**, je vidět v titulku panelu s Claudem, takže to vidíš,
i když píšeš tam — nebo když na telefonu zabere Claude celé okno a seznam
není vidět: `? shop-api čeká na schválení · ✖ infra chyba · ◆ docs-site
hotovo`. Stejné stavy jako značky v seznamu — čekající schválení
nástroje, chyba, pauza na limitu, dokončený běh, který jsi ještě neviděl —
nejnaléhavější první, bez konverzace, ve které právě jsi; co se nevejde,
skončí jako `+N další`. Když nic nečeká, zmizí. `Alt+N` otevře první
z nich.

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
  odešle, `Ctrl+J` začne nový řádek, `Ctrl+E` otevře text v
  [externím editoru](settings.md#externí-editor). `Alt+1` … `Alt+9`
  odešlou nebo vloží [přednastavený prompt](settings.md).
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

### Zaplnění kontextu

Pod tím je, jak moc je zaplněné kontextové okno, např.
`kontext 62 % · 124k / 200k`. Když se zaplní, Claude Code konverzaci sám
zkompaktuje a detaily z dřívější práce se ztratí — číslo ti to řekne
včas, abys spustil(a) `/compact` nebo založil(a) novou konverzaci. Od
80 % je žluté, od 90 % červené, s nápovědou *zvaž /compact nebo novou
konverzaci*; oba prahy jsou v [Nastavení](settings.md) → Kontext.

Počítá se z promptu poslední odpovědi Clauda (vstupní tokeny + cache,
stejně jako `/context` v Claude Code) děleno velikostí okna modelu:

- **1M**, když má `--model` konverzace `[1m]`, nebo konverzace už
  přesáhla 200k (to pojme jen 1M okno),
- okno zvolené v Nastavení → Kontext → Okno,
- jinak **200k** u modelu Claude.

U modelu, který ccc nezná, se ukážou jen tokeny bez %. Když tvůj model
běží s 1M oknem i bez `[1m]`, zvol v Nastavení *1M* — jinak vychází %
moc vysoko, dokud konverzace nepřesáhne 200k.

S nastaveným Telegramem nebo Discordem ti ccc jednou napíše, když
konverzace dosáhne varování (znovu až poté, co klesla pod něj, např. po
`/compact`); vypíná se v Nastavení → Kontext → Upozornit.

## Další klávesy

| Klávesa | |
|---|---|
| `t` | [fronta úkolů](tasks.md) této konverzace |
| `r` | zastavená chybou: znovu spustí selhaný úkol; pozastavená na limitu: pokračuje — viz [Limity využití](limits.md) |
| `p` | [schválí nástroj](approvals.md), na který Claude čeká |
| `x` | [archivuje](archive.md) konverzaci |
| `/` | hledá ve všech konverzacích (i archivovaných); `Enter` na výsledku ho otevře |
| `f` | filtruje seznam podle názvu, složky a stavu (viz *Filtr seznamu*) |
| `e` | exportuje konverzaci jako Markdown (do `conversations/` ve složce pro exporty, viz [Nastavení](settings.md)) |
| `n` | [založí novou konverzaci](new-conversation.md) |
