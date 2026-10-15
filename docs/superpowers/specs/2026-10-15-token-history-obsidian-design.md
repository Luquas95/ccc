# Historie tokenů, kalendářní měsíce a export do Obsidianu — návrh

Datum: 2026-10-15. Schváleno uživatelem v konverzaci (varianta A — historie přežije smazání;
export bez pluginů; složku zatím vytvořit v ccc, uživatel ji přesune do vaultu).

## 1. Historie přežije smazání konverzace
- `delete_queue`: smaže konverzaci, její úkoly a žádosti o schválení; v `prompt_runs` vymaže
  texty (`prompt_text`, `result_text`, `error_text`), ale řádky s tokeny, `run_model_usage` a
  `session_usage` ponechá. Název a cestu uloží do nové tabulky
  `deleted_queues(queue_id PK, name, project_path, deleted_at)`.
- `queues.id` je AUTOINCREMENT → id se nerecyklují, staré řádky nikdy nepatří nové konverzaci.

## 2. Jednotný zdroj čísel
- `Storage.token_entries(start, end)` → `(day, queue_id, model, tokens)` agregované po dnech:
  `run_model_usage` (podle modelu) + běhy bez rozpadu na modely jako `unknown` +
  `session_usage`. `Storage.conversation_names()` → `{queue_id: (name, deleted)}`.
  `Storage.run_status_counts(start, end)` → `{queue_id: (success, errors, rate_limited)}`.
- `src/ccc/token_stats.py`: `month_stats(storage, year, month)` (součet, po dnech, po modelech,
  po konverzacích), `months(storage)` (měsíce s daty a součty), `day_stats(...)`.

## 3. Analytics po kalendářních měsících
- Panely *Tokens per day*, *Tokens by model* a *Tokens per project* ukazují vybraný kalendářní
  měsíc (výchozí aktuální), `←`/`→` přepíná měsíc; v titulku měsíc a součet.
- Graf: jeden sloupec na den měsíce. Smazané konverzace v tabulce s „(deleted)“.

## 4. Měsíční archiv (Markdown pro Obsidian, bez pluginů)
*Upraveno podle uživatele: aktuální historie je jen v ccc; do `.md` se ukládá až uzavřený měsíc.*
- Složka `analytics` u dat ccc (`~/.local/share/ccc/analytics`), přenastavitelná v Settings →
  *Monthly analytics archive* / `ccc config analytics-folder PATH|default`.
- Démon jednou za hodinu archivuje každý **skončený** měsíc s daty, který ve složce ještě není:
  `YYYY-MM.md` + `YYYY-MM-DD.md` jeho dnů (zapisuje se jednou, později se nepřepisuje; smazaný
  soubor se zapíše znovu). `ccc_analytics.md` (úvodní: součet a graf archivovaných měsíců,
  odkazy) se přepíše, když přibude měsíc. Ruční `ccc archive-analytics` / tlačítko v Settings.
- Frontmatter `generator: ccc`; soubory bez něj se nepřepisují.

## Testy
Mazání (texty pryč, tokeny zůstávají, název v deleted_queues), token_entries / month_stats,
Analytics přepínání měsíců, export (struktura souborů, odkazy, součty, idempotence — žádný
zápis bez změny), CLI a Settings.
