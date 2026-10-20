# Git: automatické commity a diffy

V git repozitáři ccc commitne výsledek každého úspěšného úkolu **na
pozadí**, takže každý úkol je jeden commit, který si můžeš prohlédnout
nebo vrátit:

- zpráva `ccc: <první řádek úkolu>` s trailerem
  `ccc-conversation: <název>`;
- detail fronty (`Enter` na [Přehledu](dashboard.md)) ukazuje commit
  každého běhu; `Enter` na běhu ukáže změněné soubory a barevný diff.

## Vrácení běhu

V detailu fronty vyber běh s commitem a stiskni `u`: ccc ho vrátí
**novým commitem** (`git revert`). Nic se nepřepisuje a i vrácení jde
vrátit. Běh pak má u commitu `↺`. ccc se zeptá, jestli to má **říct
Claudovi** krátkou poznámkou ve frontě konverzace; jinak může jeho další
úkol se změnami pořád počítat.

Funguje, když:

- konverzace zrovna nic nedělá (žádný úkol neběží ani nečeká) — úkol,
  který by soubory upravoval, by své změny přimíchal do vrácení;
- ve složce nejsou necommitnuté změny a commit je v historii větve;
- konverzace byla spuštěná s **Přeskočit všechny kontroly oprávnění**
  (stejně jako samotné commity, viz níže).

Vrácení, které se pohádá s pozdějšími změnami, se zruší: nic se nezmění
a ccc to řekne. Z příkazové řádky: `ccc runs KONVERZACE` vypíše běhy
s jejich id, `ccc revert BĚH [--tell]` jeden vrátí.

## Více konverzací v jedné složce

Dvě konverzace, které upravují stejné soubory zároveň, si překážejí a
commit po úkolu jedné by mohl zahrnout rozdělané změny druhé. Proto
v jednom git pracovním stromu:

- **úkoly na pozadí se střídají**: úkol počká, dokud jiná konverzace ve
  stejné složce dokončí svůj (Konverzace ukážou kterou);
- ccc **necommitne**, když ve složce pracuje jiná konverzace (i
  interaktivní, která zrovna zpracovává, co jsi napsal) — historie běhů
  to uvede;
- Konverzace ukazují řádek ⚠ s ostatními, které složku sdílejí.

Aby mohly opravdu pracovat **vedle sebe**, dej konverzaci při
[spuštění](new-conversation.md) **vlastní git worktree**: samostatnou
pracovní kopii repozitáře na vlastní větvi (`worktree-<název>`, ve
`.claude/worktrees/<název>` — tam, kde si je drží `claude --worktree
<název>`, mimo `git status` hlavní kopie). ccc tam commituje její úkoly;
větev slouč, až budeš spokojený. Nepotřebný worktree odstraníš přes
`git worktree remove .claude/worktrees/<název>`.

## Kdy ccc necommitne

Historie běhů řekne proč:

- ve složce už před úkolem byly **necommitnuté změny** — to je tvoje
  práce, ccc ji nikdy do svého commitu nepřimíchá;
- nic se nezměnilo, nebo je repozitář na odpojeném HEAD;
- konverzace nebyla založená s **Přeskočit všechny kontroly oprávnění**.
  ccc spouští git sám, mimo režim oprávnění Clauda, takže v konverzaci
  s *Automaticky přijímat úpravy* / *Jen plán* by tam Claude jinak mohl
  podstrčit git hook, který by ccc spustil;
- config repozitáře používá filtry, includy nebo podepisování (nebo se
  během úkolu změnil) — z bezpečnosti tam pak ccc git vůbec nespouští.

Konverzace s Claude Code vedle ccc ccc necommituje — tam commituje
Claude sám, když ho o to požádáš.
