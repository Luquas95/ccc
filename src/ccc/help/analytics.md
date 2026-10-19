# Analytics

Analytics (`v`) shows how much of your Claude limits you use and what ccc
used, month by month.

![Analytics](../../../docs/screenshots/analytics.png)

## Claude Pro usage

Your account's real usage windows — **5-hour** and **weekly**, plus per
model where your plan has them — with when they reset. These are the
numbers the daemon uses to wait for resets (see
[Usage limits](limits.md)). The line under them shows your usage reserve.

## Tokens in a calendar month

`←` / `→` switch months.

- **Tokens per day** — a chart of the month.
- **Tokens by model** — each model's share of the month's tokens; the
  shares add up to 100 %.
- **Tokens per conversation** — tokens, successful runs, errors and
  rate-limited runs of each conversation.

Counted are headless runs and the replies in conversations with Claude
Code beside ccc (also replies to messages from your phone). Claude Code
sessions started outside ccc aren't counted. The history is kept for
good — also for conversations you delete (shown as *deleted*).

## Monthly archive for Obsidian

Optional: ccc can write each finished month as Markdown notes into a
folder — for example inside your Obsidian vault. Obsidian draws the
charts itself, no plugins needed.

| Note | |
|---|---|
| `ccc_analytics.md` | start page: total of all archived months, links, a chart per month |
| `2026-10.md` | a month: total, a calendar (click a day), chart per day, by model, by conversation |
| `2026-10-15.md` | a day: total, by model, by conversation |

Turn it on in [Settings](settings.md) → *Monthly analytics archive* by
choosing a folder (or `ccc config analytics-folder PATH`). The daemon then
archives each month once it ends; *Archive finished months now* (or
`ccc archive-analytics`) writes the missing ones at once. ccc never
rewrites a note once written (delete it and ccc writes it again) and never
touches files it didn't make.
