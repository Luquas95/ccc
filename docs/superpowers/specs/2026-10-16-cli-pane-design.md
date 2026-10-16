# Klasické Claude Code CLI v okně ccc — návrh

Datum: 2026-10-16. Issue #12. Uživatel chce v nové konverzaci běžnou CC session se všemi
funkcemi CLI (slash příkazy, schvalování, klávesy, vzhled), vloženou v okně ccc. Volbu
techniky nechal na mně („udělej to nějak“).

## Zvolené řešení: skutečný terminál v tmux panelu vedle ccc
Nic se neemuluje. ccc TUI běží v tmux (služba `ccc-tui`, server `ccc`). Interaktivní
`claude` běží v tmux serveru `ccc-sessions` (jako dnes remote-control konverzace, spouští
ho démon). Pro vybranou interaktivní konverzaci ccc rozdělí svoje tmux okno: vlevo zúžené
ccc (sidebar), vpravo panel s tmux klientem připojeným k relaci `claude`. Všechny funkce CC
fungují, protože je to skutečné CLI ve skutečném terminálu.

Zamítnuto: čtení obrazovky přes `capture-pane` a vykreslování v Textualu, emulátor `pyte`,
`textual-terminal` — všechno jen napodobuje terminál (myš, scrollback, obrázky, některé
klávesy), `textual-terminal` se neudržuje. Ověřeno: vnořený tmux klient v panelu předává
klávesy včetně Ctrl+B a velikost relace se přizpůsobí panelu.

## Části
1. **`DeliveryMode.INTERACTIVE`** — konverzace běží jako interaktivní `claude` v
   `ccc-sessions` (démon ji spouští, vkládá zprávy z fronty, hlídá limity, počítá tokeny
   z přepisu). `REMOTE_CONTROL` = totéž + `--remote-control`. `DeliveryMode.managed`
   pokrývá obě. Nová konverzace z `n` je vždy interaktivní (s remote control, když je
   zaškrtnuté). Headless (`claude -p`) zůstává pro `a` / `ccc add`; staré headless
   konverzace se dál zobrazují jako přepis.
2. **Průhledný server `ccc-sessions`** — při startu relace démon nastaví: bez prefixu,
   bez stavového řádku, myš zapnutá (posouvání historie), `Ctrl+]` odpojí klienta. Klávesy
   tak jdou rovnou do Claude; Ctrl+B zachytí vnější tmux (přepínání panelů).
3. **`ccc.attach_cli`** (`python -m ccc.attach_cli QUEUE_ID`) — příkaz panelu: počká, až
   démon relaci spustí („Starting Claude Code…“), pak se k ní připojí (`TMUX` vynulované,
   vnořený klient).
4. **`ccc.tui.cli_pane`** — správa panelu v tmux okně TUI: otevřít/přepnout (`split-window`
   / `respawn-pane`), zavřít, aktivovat, zjistit, jestli existuje. Panel označený volbou
   `@ccc-cli`. Úzké okno (< 100 sloupců): panel se roztáhne přes celé okno (zoom).
5. **Conversations** — vybraná interaktivní konverzace: otevře se panel (ccc se zúží na
   sidebar), `Enter` v seznamu přepne kurzor do Claude. Headless konverzace nebo odchod z
   Conversations: panel se zavře. ccc mimo tmux: v pravé části tlačítko/`Enter` „Open
   Claude Code“ — ccc se uspí (`App.suspend`) a CLI se otevře přes celou obrazovku,
   `Ctrl+]` vrátí zpět.

## Ovládání
`Ctrl+B →` / klik: do Claude · `Ctrl+B ←` / klik: zpět do ccc · `Ctrl+B z`: panel přes
celé okno · `Ctrl+]`: zavřít CLI (relace běží dál, `Enter` ji znovu otevře).

## Chyby a okraje
- Démon neběží → panel ukazuje „Starting Claude Code…“ a čeká; po 60 s napíše, že démon
  neběží.
- Archivace konverzace zastaví proces (jako dnes u remote control); panel se zavře.
- Každá otevřená interaktivní konverzace drží proces `claude` — nepotřebné archivuj.

## Testy
Jednotkové: příkaz `claude` (s/bez `--remote-control`), nastavení serveru, tmux příkazy
panelu (otevřít/přepnout/zavřít/zoom), `attach_cli` (čekání, timeout, exec), výchozí
režim nové konverzace, počítání tokenů pro oba řízené režimy, Conversations otevírá/zavírá
panel podle režimu (tmux mockovaný). Ručně: skutečná konverzace v `ccc-tmux.sh`.
