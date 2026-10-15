# Tokeny remote-control konverzací v Analytics — návrh

Datum: 2026-10-15. Schváleno uživatelem („Ano“).

## Problém
Analytics a Dashboard počítají tokeny jen z `prompt_runs` (headless běhy). Remote-control
konverzace běží jako interaktivní `claude --remote-control` a strukturovaný výsledek s tokeny
nevrací — jejich spotřeba v ccc chybí, přestože je uživatel používá často.

## Řešení
- Zdroj: přepis session (`~/.claude/projects/*/<session_id>.jsonl`) a přepisy subagentů
  (`<session_id>/subagents/*.jsonl`). Každá odpověď modelu má `message.id`, `model` a `usage`;
  jedna odpověď je na více řádcích se shodným `usage` → deduplikace podle `message.id`.
- Tabulka `session_usage(queue_id, message_id, model, at, input_tokens, output_tokens,
  cache_read_tokens, cache_creation_tokens)`, `UNIQUE(queue_id, message_id)`, `at` je lokální
  čas (jako `prompt_runs.started_at`).
- `src/ccc/session_usage.py`: `parse_usage(path, offset)` (inkrementálně, jen celé řádky),
  `UsageCollector.collect(storage)` — pro každou remote-control konverzaci dočte nové řádky,
  započítá jen zprávy s časem ≥ `queues.created_at` (žádná starší historie), přeskočí model
  `<synthetic>`, uloží `INSERT OR IGNORE`. Offsety drží v paměti; po restartu démona čte od
  začátku a duplicity zahodí UNIQUE.
- Démon: `usage_loop` každých 30 s (vlastní úloha vedle heartbeat a záloh).
- Dotazy: `total_tokens_by_model`, `daily_token_totals` sčítají `run_model_usage`/`prompt_runs`
  i `session_usage`; nové `queue_token_total(queue_id, day=None)` pro Dashboard
  (Today's tokens) a Tokens per project. Success/Errors zůstávají z běhů.
- `delete_queue` maže i `session_usage`.
- Sessions spuštěné mimo ccc se nepočítají.

## Testy
Parser (deduplikace, neúplný řádek, `<synthetic>`, offset), collector (jen RC, jen od
vytvoření, subagenti, idempotence), dotazy Storage (součty z obou zdrojů, mazání),
Dashboard/Analytics s daty z `session_usage`.
