# Git: automatické commity a diffy

V git repozitáři ccc commitne výsledek každého úspěšného úkolu **na
pozadí**, takže každý úkol je jeden commit, který si můžeš prohlédnout
nebo vrátit:

- zpráva `ccc: <první řádek úkolu>` s trailerem
  `ccc-conversation: <název>`;
- detail fronty (`Enter` na [Přehledu](dashboard.md)) ukazuje commit
  každého běhu; `Enter` na běhu ukáže změněné soubory a barevný diff.

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
