# Recenze

Claude, který právě strávil čtyřicet kroků psaním změny, ji nedokáže
dobře posoudit: pamatuje si, proč mu každý řádek připadal správný.
**Recenze** je samostatný běh Claude Code s **čistým kontextem**. Přečte,
co konverzace změnila, a skončí jedním verdiktem:

| Verdikt | |
|---|---|
| **PASS** | změny zkontroloval a chybu nenašel |
| **FAIL** | něco je špatně; řekne kde (soubor:řádek) a co |
| **PARTIAL** | část nedokázal ověřit a řekne proč |

Klávesa `v` v [Konverzacích](conversations.md) nebo v detailu fronty
otevře okno **Recenze** vybrané konverzace.

## Jak o recenzi požádat

- Volitelně napiš, **co má zkontrolovat nejdřív** („chybové cesty, ne ty
  šťastné“). Prázdné = zkontroluje, jestli jsou změny správně.
- **Dokud neprojde**: každý verdikt jiný než PASS se vrátí konverzaci
  jako úkol (nálezy) a jakmile je Claude opraví, další kolo recenzuje
  znovu. Skončí na PASS, na limitu kol (výchozí 5, nejvýš 12) nebo když
  stiskneš **Zastavit**.
- **Spustit recenzi** (`Ctrl+S`). Recenze počká, až konverzace nic nedělá
  (nic neběží ani nečeká ve frontě) a [limity využití](limits.md) to
  dovolí, pak ji spustí daemon. Okno ji průběžně ukazuje; verdikt přijde
  i na Telegram / Discord, pokud jsou nastavené.

## Co se recenzuje

Co konverzace změnila **od poslední recenze**:

1. [commity, které ccc udělal](git.md) za její úkoly;
2. bez nich necommitnuté změny v jejím git repozitáři;
3. bez gitu soubory jejích úkolů od té doby (recenzent dostane úkoly a
   co o nich Claude napsal).

Nic nového: model se nevolá, recenze řekne *nic nového*.

Recenzent **nemůže nic změnit ani spustit**: umí jen číst a hledat
v souborech, všechno ostatní se odmítne. Diff mu připraví ccc. Načte jen
tvoje vlastní nastavení Claude Code, žádné z recenzovaného projektu
(žádná oprávnění, hooky ani MCP servery z toho repozitáře). Jeho běh se
neukládá jako relace Claude Code; jeho tokeny se počítají v
[Analytice](analytics.md) jako u úkolu.

## Po verdiktu

Vyber recenzi v seznamu a přečti si zprávu. U FAIL / PARTIAL tlačítko
**Poslat nálezy do konverzace** přidá nálezy jako úkol (režim „dokud
neprojde“ to dělá sám).

Model recenzenta je v [Nastavení](settings.md) → Fronty → *Model
recenzenta*: výchozí je model konverzace. Silný model se tu vyplatí:
přehlédnutá chyba stojí víc než recenze.

Z příkazové řádky: `ccc review` (viz [Příkazová řádka](command-line.md)).
S `--wait` je návratový kód verdikt, např. pro CI.
