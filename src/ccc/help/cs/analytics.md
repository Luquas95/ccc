# Analytika

Analytika (`v`) ukazuje, kolik ze svých limitů Clauda využíváš a kolik
spotřebovalo ccc, měsíc po měsíci.

![Analytika](../../../../docs/screenshots/analytics.png)

## Využití Claude Pro

Skutečná okna využití tvého účtu — **5hodinové** a **týdenní**, plus po
modelech, pokud je tvůj tarif má — i s tím, kdy se obnoví. Podle těchto
čísel daemon čeká na obnovení (viz [Limity využití](limits.md)). Řádek
pod nimi ukazuje tvou rezervu využití.

## Tokeny v kalendářním měsíci

`←` / `→` přepínají měsíce.

- **Tokeny po dnech** — graf měsíce.
- **Tokeny podle modelu** — podíl každého modelu na tokenech měsíce;
  podíly dávají dohromady 100 %.
- **Tokeny podle konverzace** — tokeny, úspěšné běhy, chyby a běhy
  zastavené limitem pro každou konverzaci.

Počítají se běhy na pozadí a odpovědi v konverzacích s Claude Code vedle
ccc (i odpovědi na zprávy z telefonu). Relace Claude Code spuštěné mimo
ccc se nepočítají. Historie se drží napořád — i u konverzací, které
smažeš (jako *smazaná*).

## Měsíční archiv pro Obsidian

Volitelně: ccc umí každý skončený měsíc zapsat jako Markdown poznámky do
složky — třeba do tvého trezoru v Obsidianu. Grafy si Obsidian nakreslí
sám, žádné pluginy nejsou potřeba.

| Poznámka | |
|---|---|
| `ccc_analytics.md` | úvodní stránka: součet všech archivovaných měsíců, odkazy, graf po měsících |
| `2026-10.md` | měsíc: součet, kalendář (klikni na den), graf po dnech, podle modelu, podle konverzace |
| `2026-10-15.md` | den: součet, podle modelu, podle konverzace |

Zapneš ho v [Nastavení](settings.md) → *Měsíční archiv analytiky* výběrem
složky (nebo `ccc config analytics-folder CESTA`). Daemon pak každý měsíc
archivuje, jakmile skončí; *Archivovat skončené měsíce hned* (nebo
`ccc archive-analytics`) zapíše chybějící hned. Jednou zapsanou poznámku
ccc nikdy nepřepisuje (smaž ji a ccc ji zapíše znovu) a nikdy nesahá na
soubory, které nevytvořil. Poznámky se píšou v jazyce ccc.
