"""Token history as Markdown notes for an Obsidian vault (no plugins needed).

Writes into the folder set in Settings (`obsidian_folder`):

- `ccc_analytics.md` — start page: total, months with links, a chart per
  month and this month's calendar with links to the days,
- `YYYY-MM.md` — one per month: total, calendar, chart per day, by model and
  by conversation,
- `YYYY-MM-DD.md` — one per day with usage: total, by model, by conversation.

The numbers come from the ccc database (token_stats); the notes are a view
that's regenerated — edits made in Obsidian are overwritten. A file is only
written when its content changed (no needless sync churn), and files ccc
didn't create are never touched: each generated note carries
`generator: ccc` in its frontmatter."""
from __future__ import annotations

import calendar
import logging
from datetime import date
from pathlib import Path

from ccc.token_stats import PeriodStats, day_stats, month_bounds, month_stats, months

logger = logging.getLogger(__name__)

FOLDER_KEY = "obsidian_folder"
INDEX_NAME = "ccc_analytics"
EXPORT_INTERVAL_SECONDS = 300.0
MARKER = "generator: ccc"


def _fmt(tokens: int) -> str:
    return f"{tokens:,}".replace(",", " ")


def _short(tokens: int) -> str:
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f} M"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.0f} k"
    return str(tokens)


def _month_name(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%B %Y")


def _frontmatter(**fields) -> str:
    lines = ["---", MARKER]
    lines += [f"{key}: {value}" for key, value in fields.items()]
    return "\n".join(lines + ["---", ""])


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _calendar(year: int, month: int, by_day: dict[date, int], today: date | None = None) -> str:
    """Month grid, Monday first; days with usage link to their note, today
    is bold."""
    rows = ["| Mon | Tue | Wed | Thu | Fri | Sat | Sun |", "|---|---|---|---|---|---|---|"]
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        cells = []
        for day in week:
            if day == 0:
                cells.append(" ")
                continue
            d = date(year, month, day)
            tokens = by_day.get(d, 0)
            cell = f"[[{d.isoformat()}\\|{day}]]<br>{_short(tokens)}" if tokens else str(day)
            cells.append(f"**{cell}**" if d == today else cell)
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _bar_chart(title: str, labels: list[str], values_m: list[float]) -> str:
    """Mermaid bar chart (Obsidian renders it natively); values in millions."""
    label_list = ", ".join(f'"{label}"' for label in labels)
    values = ", ".join(f"{v:.2f}" for v in values_m)
    return "\n".join([
        "```mermaid",
        "xychart-beta",
        f'    title "{title}"',
        f"    x-axis [{label_list}]",
        '    y-axis "Million tokens"',
        f"    bar [{values}]",
        "```",
    ])


def _breakdown(stats: PeriodStats) -> str:
    out = ["## By model", "", "| Model | Tokens |", "|---|---:|"]
    out += [f"| {_md_cell(model)} | {_fmt(tokens)} |" for model, tokens in stats.by_model] or ["| — | 0 |"]
    out += ["", "## By conversation", "", "| Conversation | Tokens | Success | Errors |", "|---|---:|---:|---:|"]
    for c in stats.by_conversation:
        name = _md_cell(c.name) + (" *(deleted)*" if c.deleted else "")
        out.append(f"| {name} | {_fmt(c.tokens)} | {c.success} | {c.errors} |")
    if not stats.by_conversation:
        out.append("| — | 0 | 0 | 0 |")
    return "\n".join(out)


def render_day(storage, day: date) -> str:
    stats = day_stats(storage, day)
    month_link = f"[[{day:%Y-%m}|{_month_name(day.year, day.month)}]]"
    return "\n".join([
        _frontmatter(date=day.isoformat(), tokens=stats.total),
        f"# {day:%A %d %B %Y}",
        "",
        f"**{_fmt(stats.total)} tokens** · {month_link} · [[{INDEX_NAME}|All months]]",
        "",
        _breakdown(stats),
        "",
    ])


def render_month(storage, year: int, month: int) -> str:
    stats = month_stats(storage, year, month)
    start, end = month_bounds(year, month)
    days = (end - start).days
    series = [stats.by_day.get(date(year, month, d), 0) / 1_000_000 for d in range(1, days + 1)]
    return "\n".join([
        _frontmatter(month=f"{year:04d}-{month:02d}", tokens=stats.total),
        f"# {_month_name(year, month)}",
        "",
        f"**{_fmt(stats.total)} tokens** · [[{INDEX_NAME}|All months]]",
        "",
        _calendar(year, month, stats.by_day, date.today()),
        "",
        _bar_chart(f"Tokens per day — {_month_name(year, month)}", [str(d) for d in range(1, days + 1)], series),
        "",
        _breakdown(stats),
        "",
    ])


def render_index(storage, today: date | None = None) -> str:
    today = today or date.today()
    all_months = months(storage)
    total = sum(t for _y, _m, t in all_months)
    this_month = month_stats(storage, today.year, today.month)
    out = [
        _frontmatter(tokens=total, updated=today.isoformat()),
        "# ccc analytics",
        "",
        f"**{_fmt(total)} tokens in total** — headless runs and remote-control conversations started "
        "through ccc. Generated by ccc; edits here are overwritten.",
        "",
        f"## {_month_name(today.year, today.month)} — {_fmt(this_month.total)} tokens",
        "",
        _calendar(today.year, today.month, this_month.by_day, today),
        "",
        "## Months",
        "",
        "| Month | Tokens |",
        "|---|---:|",
    ]
    out += [f"| [[{y:04d}-{m:02d}\\|{_month_name(y, m)}]] | {_fmt(t)} |" for y, m, t in all_months] or ["| — | 0 |"]
    if all_months:
        last = list(reversed(all_months[:12]))
        out += ["", _bar_chart("Tokens per month", [f"{y:04d}-{m:02d}" for y, m, _ in last],
                               [t / 1_000_000 for _y, _m, t in last])]
    return "\n".join(out + [""])


def _made_by_ccc(text: str) -> bool:
    parts = text.split("---", 2)
    return text.startswith("---") and len(parts) == 3 and MARKER in parts[1].splitlines()


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if not _made_by_ccc(current):
            logger.warning("Obsidian export: %s wasn't made by ccc, leaving it alone", path.name)
            return False
        if current == content:
            return False
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
    return True


def export(storage, folder: str | Path, today: date | None = None) -> int:
    """Write all notes into folder (created if needed); returns how many
    files were (re)written."""
    root = Path(folder).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    written = 0
    days: set[date] = set()
    for y, m, _t in months(storage):
        written += _write_if_changed(root / f"{y:04d}-{m:02d}.md", render_month(storage, y, m))
        days |= set(month_stats(storage, y, m).by_day)
    for d in sorted(days):
        written += _write_if_changed(root / f"{d.isoformat()}.md", render_day(storage, d))
    written += _write_if_changed(root / f"{INDEX_NAME}.md", render_index(storage, today))
    return written


def configured_folder(storage) -> str | None:
    folder = (storage.get_setting(FOLDER_KEY) or "").strip()
    return folder or None
