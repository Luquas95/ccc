"""Monthly archive of the token history as Markdown notes (Obsidian-friendly,
no plugins needed).

The current month lives only in ccc (Analytics). When a month is over, the
daemon archives it — once — into the analytics folder (default
`~/.local/share/ccc/analytics`, next to the database; Settings can point it
into an Obsidian vault):

- `YYYY-MM.md` — the month: total, calendar with links to the days, chart per
  day, by model and by conversation,
- `YYYY-MM-DD.md` — each day of it with usage: total, by model, by conversation,
- `ccc_analytics.md` — start page: total and chart of the archived months,
  links to them. Rewritten whenever a month is added.

Archived notes aren't rewritten later (deleting one makes ccc write it again).
Files ccc didn't create are never touched: generated notes carry
`generator: ccc` in their frontmatter."""
from __future__ import annotations

import calendar
import logging
from datetime import date
from pathlib import Path

from ccc.token_stats import PeriodStats, day_stats, month_bounds, month_stats, months

logger = logging.getLogger(__name__)

FOLDER_KEY = "analytics_folder"
INDEX_NAME = "ccc_analytics"
ARCHIVE_CHECK_SECONDS = 3600.0
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
        _calendar(year, month, stats.by_day),
        "",
        _bar_chart(f"Tokens per day — {_month_name(year, month)}", [str(d) for d in range(1, days + 1)], series),
        "",
        _breakdown(stats),
        "",
    ])


def render_index(archived: list[tuple[int, int, int]]) -> str:
    """Start page over the archived (finished) months, newest first."""
    total = sum(t for _y, _m, t in archived)
    out = [
        _frontmatter(tokens=total, months=len(archived)),
        "# ccc analytics",
        "",
        f"**{_fmt(total)} tokens in archived months** — headless runs and remote-control conversations "
        "started through ccc. A month is archived here when it ends; the current month is in ccc → "
        "Analytics (`v`). Generated by ccc.",
        "",
        "## Months",
        "",
        "| Month | Tokens |",
        "|---|---:|",
    ]
    out += [f"| [[{y:04d}-{m:02d}\\|{_month_name(y, m)}]] | {_fmt(t)} |" for y, m, t in archived] or [
        "| — *(nothing archived yet)* | 0 |"]
    if archived:
        last = list(reversed(archived[:12]))
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


def _write_new(path: Path, content: str) -> bool:
    """Archive notes are written once; an existing file is left as it is."""
    if path.exists():
        return False
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
    return True


def archive(storage, folder: str | Path, today: date | None = None) -> list[tuple[int, int]]:
    """Archive every finished month with usage that isn't in folder yet
    (the folder is created if needed) and refresh the start page. Returns
    the newly archived (year, month)."""
    today = today or date.today()
    root = Path(folder).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    finished = [(y, m, t) for y, m, t in months(storage) if (y, m) < (today.year, today.month)]
    added = []
    for y, m, _t in finished:
        month_file = root / f"{y:04d}-{m:02d}.md"
        if month_file.exists():
            continue
        for d in month_stats(storage, y, m).by_day:
            _write_new(root / f"{d.isoformat()}.md", render_day(storage, d))
        _write_new(month_file, render_month(storage, y, m))
        added.append((y, m))
    archived = [(y, m, t) for y, m, t in finished if (root / f"{y:04d}-{m:02d}.md").exists()]
    _write_if_changed(root / f"{INDEX_NAME}.md", render_index(archived))
    return added


def default_folder(storage) -> Path:
    return Path(storage.db_path).parent / "analytics"


def configured_folder(storage) -> Path:
    folder = (storage.get_setting(FOLDER_KEY) or "").strip()
    return Path(folder).expanduser() if folder else default_folder(storage)
