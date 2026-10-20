# Goal loop (smyčka k cíli)

Řekni jednou, **jak vypadá hotovo**, a ccc nechá konverzaci pracovat,
dokud to nezávislý recenzent nepotvrdí. Nemusíš kontrolovat každý pokus
a psát „zkus to znovu“.

Klávesa `g` v [Konverzacích](conversations.md) nebo v detailu fronty
otevře okno **Cíl** vybrané konverzace.

## Zadání cíle

- **Cíl**: dost konkrétní, aby se dal ověřit. „Auth middleware odmítá
  vypršelé tokeny a test to dokazuje“ funguje; „vylepši auth“ ne.
- **Kontrolní příkaz** (volitelný): spustí se po každém kole ve složce
  projektu, např. `pytest -q` nebo `npm test && npm run lint`. ccc ho
  spouští jen v konverzacích spuštěných s *Přeskočit všechny kontroly
  oprávnění*, kde Claude smí spustit jakýkoli příkaz i tak; jinde se
  kontrola vynechá.
- **Kola**: nejvýš tolik (výchozí 5, maximum 20).
- **Spustit** (`Ctrl+S`): první úkol, tedy cíl, přijde do
  [fronty úkolů](tasks.md) konverzace.

## Jedno kolo

1. Claude pracuje na úkolu jako na každém jiném ve frontě.
2. ccc spustí kontrolní příkaz. Když selže, kolo hned neprojde a jeho
   výstup jde zpět Claudovi; na rozbitý build není potřeba recenzent.
3. Nezávislý [recenzent](review.md) (čistý kontext, nic nemůže změnit)
   posoudí kód podle cíle: **PASS** jen když je cíl splněný celý.
4. PASS smyčku ukončí. Jinak se zpráva recenzenta stane úkolem dalšího
   kola.

## Když se to zasekne

Poslat stejnou chybu zpět stejným způsobem málokdy pomůže, proto:

| Kolo | Co se změní |
|---|---|
| 1, 2 | nic; důvod jde zpět Claudovi |
| od 3 | **recenzent** běží na silnějším modelu (Opus), kdyby chyboval on |
| od 4 | silnější model dostane i **Claude** (konverzace na pozadí; interaktivní si model nechá) |
| 5 | Claude dostane pokyn přestat záplatovat a promyslet přístup |

## Kdy skončí

- **splněno**: recenzent řekl PASS;
- **zaseknuto**: dvakrát po sobě stejná chyba (stejný důvod verdiktu nebo
  stejný výstup kontroly);
- **došla kola**: dosažen limit;
- **selhalo**: úkol smyčky selhal (viz konverzace) nebo byl z fronty
  odebrán;
- **zastaveno**: stiskl(a) jsi **Zastavit**. Čekající úkol se přeskočí,
  rozběhnutý doběhne.

Jak to skončilo, přijde na Telegram / Discord, pokud jsou nastavené.
Každé kolo je skutečný úkol a skutečná recenze: obojí se počítá do
využití.

Z příkazové řádky: `ccc goal` (viz [Příkazová řádka](command-line.md)).
S `--wait` je návratový kód 0, když je cíl splněný, jinak 1.
