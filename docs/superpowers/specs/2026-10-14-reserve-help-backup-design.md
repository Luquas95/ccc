# Rezerva využití, nápověda kláves, záloha DB — návrh

Datum: 2026-10-14

## 3. Rezerva využití
- `ccc config usage-reserve <0-100>` (`off` vypne; výchozí vypnuto),
  setting `usage_reserve`.
- Před spuštěním/doručením úkolu (headless i remote control) démon kromě
  vyčerpání (100 %) kontroluje i práh: je-li 5h nebo týdenní okno
  (i per-model) ≥ práh, úkol nespustí, fronta přejde do `waiting_retry`
  do resetu toho okna (+30 s) bez ohledu na auto-continue a `last_error`
  = `usage reserve N%`. Rozběhnutý úkol doběhne.
- Stavový řádek: „Holding for usage reserve (N%) until HH:MM“. Telegram:
  „‖ <název>: usage above your N% reserve — waiting until HH:MM“.
- `limits.exhausted_until(usage, now, threshold=100)`.

## 8. Nápověda kláves
- `?` na každé obrazovce (`SidebarScreen`) otevře okno se všemi zkratkami
  po obrazovkách (globální, Conversations, Tasks, okna). Esc / ? zavře.

## 9. Záloha databáze
- Démon jednou denně (při startu a pak každých 24 h; den určuje název
  souboru) uloží `~/.local/share/ccc/backups/history-YYYY-MM-DD.db` přes
  `sqlite3.Connection.backup` (konzistentní i za běhu), práva 600,
  ponechá 14 nejnovějších. Existuje-li dnešní záloha, nic nedělá.
- `ccc backup` udělá zálohu hned (přepíše dnešní) a vypíše cestu.
