# Přehled

Přehled (`d`) ukazuje všechny konverzace a to, co zrovna dělají. Slouží
jen k dívání — s konverzací pracuješ v [Konverzacích](conversations.md).

![Přehled](../../../../docs/screenshots/dashboard.png)

## Souhrn

Horní řádek sčítá všechny konverzace: na kolika Claude pracuje
(**běží**), kolik úkolů čeká v jejich frontách (**čeká**), kolik se jich
zastavilo chybou (**zablokované**, červeně) a kolik tokenů dnes spotřebovaly.

## Tabulka

Jeden řádek na konverzaci (archivované jsou v [Archivu](archive.md)):

| Sloupec | |
|---|---|
| Projekt | název konverzace se značkou (viz níže) |
| Stav | co dělá — viz tabulka níže |
| Čeká | úkoly čekající v její [frontě](tasks.md) |
| Tokeny dnes | tokeny, které dnes spotřebovala |
| Cesta | složka projektu, ve které Claude pracuje |

**Značky** před názvem — stejné jako v seznamu Konverzací:

| Značka | Význam |
|---|---|
| `●` | Claude pracuje |
| `‖` | čeká na obnovení limitu využití, nebo je pozastavená |
| `✖` | zastavila se chybou — potřebuje tě |
| `?` | Claude čeká, až [schválíš nástroj](approvals.md) |
| `◆` | nová odpověď, kterou jsi ještě neviděl(a) |

V seznamu Konverzací znamená `·3` za názvem tři úkoly ve frontě.

**Stav:**

| Stav | |
|---|---|
| `nečinná` | nemá co dělat; další úkol začne, jakmile nějaký přidáš |
| `běží` | Claude pracuje na úkolu |
| `čeká na opakování` | čeká na obnovení limitu využití; pak sama pokračuje |
| `pauza na limitu` | zastavila se na limitu využití s vypnutým automatickým pokračováním — čeká na tebe |
| `zablokovaná chybou` | zastavila se chybou — čeká na tebe |

Co s posledními dvěma: [Limity využití a zablokované fronty](limits.md).

## Detail fronty

`Enter` na řádku otevře detail konverzace:

- její nastavení (složka, volby Claude Code, automatické pokračování)
  a u konverzace se [vzdáleným ovládáním](remote-control.md) odkaz, jak
  ji otevřít v telefonu;
- **historii běhů**: každý úkol s výsledkem, tokeny a — v git
  repozitáři — commitem. `Enter` na běhu ukáže diff commitu (viz
  [Git](git.md));
- `a` přidá konverzaci úkol, `r` ji znovu rozběhne, když je zablokovaná
  nebo pozastavená na limitu. `Esc` vrací zpět.

![Detail fronty](../../../../docs/screenshots/queue_detail.png)

## Prázdný Přehled

Před první konverzací ukazuje Přehled místo tabulky **Začínáme** — tři
kroky na začátek. Stiskni `n`.
