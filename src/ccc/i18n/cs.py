"""Czech catalogue: English source string -> Czech. Grouped by where the
string is used; tests/test_i18n.py keeps it complete and free of unused
entries. Keys, placeholders ({name}) and Rich markup ([b]…[/b]) stay as
they are."""

CS: dict[str, str] = {
    # --- shared words --------------------------------------------------------
    "Dashboard": "Přehled",
    "Conversations": "Konverzace",
    "Archive": "Archiv",
    "Live sessions": "Živé relace",
    "Analytics": "Analytika",
    "Settings": "Nastavení",
    "Help": "Nápověda",
    "Close": "Zavřít",
    "Back": "Zpět",
    "Cancel": "Zrušit",
    "Save": "Uložit",
    "Add": "Přidat",
    "Edit": "Upravit",
    "Delete": "Smazat",
    "Yes": "Ano",
    "No": "Ne",
    "Send": "Odeslat",
    "Sent": "Odesláno",
    "Search": "Hledat",
    "Status": "Stav",
    "Tokens": "Tokeny",
    "Conversation": "Konverzace",
    "Queue": "Fronta",
    "Queues": "Fronty",
    "⏎ sends  ·  ✎ inserts": "⏎ odešle  ·  ✎ vloží",
    "Project": "Projekt",
    "Path": "Cesta",
    "Prompt": "Prompt",
    "Name": "Název",
    "When": "Kdy",
    "Task": "Úkol",
    "Tasks": "Úkoly",
    "Model": "Model",
    "Month": "Měsíc",
    "Months": "Měsíce",
    "Success": "Úspěšné",
    "Errors": "Chyby",
    "Folder": "Složka",
    "Preset": "Předvolba",
    "You": "Ty",
    "on": "zapnuto",
    "off": "vypnuto",
    "Off": "Vypnuto",
    "never": "nikdy",
    "running": "běží",
    "paused": "pozastaveno",
    "starting…": "spouští se…",
    "default": "výchozí",
    "(deleted)": "(smazaná)",
    " (deleted)": " (smazaná)",
    "{tokens} tokens": "{tokens} tokenů",
    "Ctrl+S save  ·  Esc cancel": "Ctrl+S uložit  ·  Esc zrušit",
    "/path/to/project": "/cesta/k/projektu",

    # --- queue / run / delivery states ----------------------------------------
    "idle": "nečinná",
    "waiting_retry": "čeká na opakování",
    "blocked_error": "zablokovaná chybou",
    "paused_limit": "pauza na limitu",
    "success": "úspěch",
    "rate_limited": "limit",
    "error": "chyba",
    "headless": "na pozadí",
    "interactive": "interaktivní",
    "live_terminal": "živý terminál",
    "remote_control": "vzdálené ovládání",
    "busy": "pracuje",
    "blocked": "blokovaná",
    "background": "na pozadí",

    # --- frame (tui/layout.py) -------------------------------------------------
    "Add prompt (a)": "Přidat prompt (a)",
    "Retry blocked queue (r)": "Znovu spustit frontu (r)",
    "New conversation (n)": "Nová konverzace (n)",
    "New conversation": "Nová konverzace",
    "y / Enter yes  ·  n / Esc no": "y / Enter ano  ·  n / Esc ne",
    "Esc close": "Esc zavřít",
    "● daemon running": "● daemon běží",
    "✖ daemon not running — queues are stopped": "✖ daemon neběží — fronty stojí",

    # --- Dashboard ------------------------------------------------------------
    "[b]No conversations yet.[/b] Three steps to your first one:\n\n"
    "  [b cyan]1.[/]  Press [b]n[/b] (or New conversation in Conversations), pick a project folder,\n"
    "      tick the Claude Code options you want, Start.\n"
    "  [b cyan]2.[/]  Claude Code opens beside ccc in Conversations — talk to it as in a terminal.\n"
    "  [b cyan]3.[/]  Queue more work with [b]t[/b]. ccc carries on when you close it (Ctrl+Q)\n"
    "      and waits out usage limits by itself.\n\n"
    "Press [b]?[/b] for the guide — every screen, every key.":
        "[b]Zatím žádná konverzace.[/b] Tři kroky k té první:\n\n"
        "  [b cyan]1.[/]  Stiskni [b]n[/b] (nebo Nová konverzace v Konverzacích), vyber složku projektu,\n"
        "      zaškrtni volby pro Claude Code a dej Spustit.\n"
        "  [b cyan]2.[/]  Claude Code se otevře vedle ccc v Konverzacích — mluv s ním jako v terminálu.\n"
        "  [b cyan]3.[/]  Další práci zařaď do fronty klávesou [b]t[/b]. ccc pokračuje i po zavření (Ctrl+Q)\n"
        "      a limity využití sám přečká.\n\n"
        "Stiskni [b]?[/b] pro nápovědu — každá obrazovka, každá klávesa.",
    "Overview": "Souhrn",
    "Getting started": "Začínáme",
    "Pending": "Čeká",
    "Today's tokens": "Tokeny dnes",
    "{n} blocked": "zablokované: {n}",
    "{n} running": "běží: {n}",
    "[b]{queues}[/b] queues  ·  {running}  ·  [b]{pending}[/b] pending  ·  {blocked}  ·  "
    "[b]{tokens}[/b] tokens today":
        "fronty: [b]{queues}[/b]  ·  {running}  ·  čeká: [b]{pending}[/b]  ·  {blocked}  ·  "
        "tokeny dnes: [b]{tokens}[/b]",

    # --- Queue detail -----------------------------------------------------------
    "Queue detail": "Detail fronty",
    "Retry blocked": "Znovu spustit",
    "Add prompt": "Přidat prompt",
    "Run history": "Historie běhů",
    "Started": "Začátek",
    "Commit": "Commit",
    "Result": "Výsledek",
    "No commit": "Bez commitu",
    "Status: {status}   ·   Pending: [b]{pending}[/b]   ·   Delivery: {delivery}":
        "Stav: {status}   ·   Čeká: [b]{pending}[/b]   ·   Doručení: {delivery}",
    "Launch: {flags}": "Spuštění: {flags}",
    "auto-continue on": "automatické pokračování zapnuto",
    "auto-continue off": "automatické pokračování vypnuto",
    "  ·  queue paused": "  ·  fronta pozastavena",
    "Session: ": "Relace: ",
    "Remote control: ": "Vzdálené ovládání: ",
    "First run: ": "První běh: ",
    "Next retry: ": "Další pokus: ",
    "Last error: ": "Poslední chyba: ",
    "Project path": "Cesta k projektu",
    "New prompt": "Nový prompt",
    "Both path and prompt are required.": "Vyplň cestu i prompt.",
    "Commit {commit}  ·  Esc close": "Commit {commit}  ·  Esc zavřít",

    # --- Conversations / Archive ------------------------------------------------
    "NO CONVERSATION": "BEZ KONVERZACE",
    "EMPTY": "PRÁZDNO",
    "Retry / resume": "Znovu / pokračovat",
    "Export conversation": "Export konverzace",
    "Approve": "Schválit",
    "Close Claude": "Zavřít Claude",
    "Restore": "Obnovit",
    "Preset {n}": "Předvolba {n}",
    "Message Claude… (Enter send · Ctrl+J new line · Esc back)":
        "Zpráva pro Clauda… (Enter odeslat · Ctrl+J nový řádek · Esc zpět)",
    "Can't open Claude Code here ({error}).": "Claude Code tady nejde otevřít ({error}).",
    "No conversation yet.": "Zatím žádná konverzace.",
    "… {n} earlier messages not shown": "… starší zprávy nezobrazeny: {n}",
    "(no output)": "(bez výstupu)",
    "queued": "ve frontě",
    "(waiting for result…)": "(čeká na výsledek…)",
    "archived: ": "archivováno: ",
    "x restores it, Enter restores and opens it, Delete deletes it":
        "x obnoví, Enter obnoví a otevře, Delete smaže",
    "remote control: ": "vzdálené ovládání: ",
    "Enter in the list opens it": "Enter v seznamu ho otevře",
    " (full screen, Ctrl+] back)": " (přes celou obrazovku, Ctrl+] zpět)",
    "first run: ": "první běh: ",
    "? Waiting for your approval: {tool} — press p": "? Čeká na tvé schválení: {tool} — stiskni p",
    "  ·  {n} queued": "  ·  ve frontě: {n}",
    "● Claude is working…": "● Claude pracuje…",
    "‖ Holding for your usage reserve ({percent}) until {time}": "‖ Drží rezervu využití ({percent}) do {time}",
    "‖ Waiting for usage limit reset until {time}": "‖ Čeká na obnovení limitu do {time}",
    "‖ Paused at usage limit, resets {time}": "‖ Pozastaveno na limitu, obnoví se v {time}",
    "‖ Limit reset — press r to continue": "‖ Limit obnoven — stiskni r a pokračuj",
    "‖ Queue paused — t, p to resume": "‖ Fronta pozastavena — t, p obnoví",
    "✖ Blocked: {error} — press r to retry": "✖ Zablokováno: {error} — stiskni r pro nový pokus",
    "Ready": "Připraveno",
    "Next task at {time}": "Další úkol v {time}",
    "No preset on Alt+{n} — add one in Settings (Ctrl+P).": "Na Alt+{n} není předvolba — přidej ji v Nastavení (Ctrl+P).",
    "Select a conversation first.": "Nejdřív vyber konverzaci.",
    "Can't delete": "Nejde smazat",
    "Claude is working on '{name}' right now — wait or pause it first (t, p).":
        "Claude právě pracuje na '{name}' — počkej, nebo ji nejdřív pozastav (t, p).",
    "Delete conversation": "Smazat konverzaci",
    "Delete '{name}' with its queued tasks and run history from ccc?\n"
    "Claude Code's own transcript stays, so it can still be resumed later.":
        "Smazat '{name}' z ccc i s úkoly ve frontě a historií běhů?\n"
        "Přepis v Claude Code zůstane, takže se dá později obnovit.",
    "Exported to {path}": "Exportováno do {path}",
    "Nothing is waiting for approval in this conversation.": "V této konverzaci nic nečeká na schválení.",

    # --- Tasks --------------------------------------------------------------------
    "New task": "Nový úkol",
    "Edit task": "Upravit úkol",
    "Run at (empty = as soon as possible; HH:MM · YYYY-MM-DD HH:MM · reset)":
        "Spustit v (prázdné = co nejdřív; HH:MM · RRRR-MM-DD HH:MM · reset)",
    "as soon as possible": "co nejdřív",
    "Move up": "Posunout nahoru",
    "Move down": "Posunout dolů",
    "Pause/resume": "Pozastavit/obnovit",
    "Auto-continue": "Automatické pokračování",
    "a add  ·  e/Enter edit  ·  Del delete  ·  Ctrl+↑/↓ move  ·  p pause/resume  ·  o auto-continue  ·  Esc close":
        "a přidat  ·  e/Enter upravit  ·  Del smazat  ·  Ctrl+↑/↓ posunout  ·  p pozastavit/obnovit  ·  "
        "o automatické pokračování  ·  Esc zavřít",
    "Tasks — {name}": "Úkoly — {name}",
    "Auto-continue: ": "Automatické pokračování: ",
    "Queue: ": "Fronta: ",

    # --- New conversation -------------------------------------------------------
    "Save as preset": "Uložit jako předvolbu",
    "Preset name (an existing one is overwritten)": "Název předvolby (stejnojmenná se přepíše)",
    "e.g. opus-deep": "např. opus-deep",
    "Choose a preset…": "Vyber předvolbu…",
    "PR number or URL": "Číslo nebo URL pull requestu",
    "Auto-continue after usage limit": "Automaticky pokračovat po limitu využití",
    "Remote control (phone / claude.ai)": "Vzdálené ovládání (telefon / claude.ai)",
    "Recent directories": "Nedávné složky",
    "Browse": "Procházet",
    "Name (optional)": "Název (nepovinný)",
    "defaults to the directory name": "výchozí je název složky",
    "Start": "Spustit",
    "{time} · {n} msgs · {prompt}": "{time} · zprávy: {n} · {prompt}",
    "Choose a directory.": "Vyber složku.",
    # launch options (launch_options.py)
    "Session": "Relace",
    "New session": "Nová relace",
    "new": "nová",
    "Continue last in directory": "Pokračovat v poslední ve složce",
    "continue": "pokračování",
    "Resume selected…": "Obnovit vybranou…",
    "resume": "obnovení",
    "From pull request…": "Z pull requestu…",
    "from PR": "z PR",
    "As a copy (fork)": "Jako kopie (fork)",
    "fork": "fork",
    "Permissions": "Oprávnění",
    "Skip all permission checks": "Přeskočit všechny kontroly oprávnění",
    "skip permissions": "bez kontrol oprávnění",
    "Auto-accept edits": "Automaticky přijímat úpravy",
    "accept edits": "přijímat úpravy",
    "Plan only": "Jen plán",
    "plan only": "jen plán",
    "Opus": "Opus",
    "Sonnet": "Sonnet",
    "Haiku": "Haiku",
    "Fable": "Fable",
    "Effort": "Úsilí",
    "high": "high",
    "effort high": "úsilí high",
    "xhigh": "xhigh",
    "effort xhigh": "úsilí xhigh",
    "max": "max",
    "effort max": "úsilí max",
    "Other": "Ostatní",
    "Fallback to Sonnet when overloaded": "Při přetížení přejít na Sonnet",
    "fallback Sonnet": "záložní Sonnet",
    "Claude in Chrome": "Claude v Chromu",
    "Chrome": "Chrome",
    "Safe mode (no customizations)": "Bezpečný režim (bez přizpůsobení)",
    "safe mode": "bezpečný režim",
    "legacy (skip permissions)": "starší (bez kontrol oprávnění)",

    # --- Approvals ----------------------------------------------------------------
    "Allow": "Povolit",
    "Always allow": "Vždy povolit",
    "Deny": "Zamítnout",
    "Later": "Později",
    "Claude wants to use ": "Claude chce použít ",
    "y allow  ·  a always allow {tool} in this conversation  ·  n deny  ·  Esc later":
        "y povolit  ·  a vždy povolit {tool} v této konverzaci  ·  n zamítnout  ·  Esc později",
    "Approval needed": "Je potřeba schválení",

    # --- Preset prompts ---------------------------------------------------------
    "send": "odeslat",
    "insert": "vložit",
    "New preset prompt": "Nový přednastavený prompt",
    "Name (shown in the bar under the message box)": "Název (zobrazí se v liště pod polem pro zprávu)",
    "e.g. Tests": "např. Testy",
    "Send right away (with Enter) — otherwise only put into the message box":
        "Odeslat hned (s Enterem) — jinak jen vložit do pole pro zprávu",
    "No preset prompts — add them in Settings (Ctrl+P)": "Žádné přednastavené prompty — přidej je v Nastavení (Ctrl+P)",

    # --- Search / exports -------------------------------------------------------
    "Search all conversations… (Enter)": "Hledat ve všech konverzacích… (Enter)",
    "Who": "Kdo",
    "Match": "Shoda",
    "{n} matches — ↓ then Enter opens one": "Nalezeno: {n} — ↓ a Enter výsledek otevře",
    "No matches.": "Nic nenalezeno.",
    "Sent to {target}": "Odesláno na {target}",
    "Check {target} in Settings (Ctrl+P), or the file is too big.":
        "Zkontroluj {target} v Nastavení (Ctrl+P), nebo je soubor moc velký.",
    "Not sent to {target}": "Neodesláno na {target}",
    "Screenshot saved": "Snímek obrazovky uložen",
    "⌨ typing here": "⌨ píšeš sem",

    # --- Live sessions ------------------------------------------------------------
    "Reload session list (r)": "Načíst relace znovu (r)",
    "Reload session list": "Načíst relace znovu",
    "Enter on a session to send it a prompt — typed into its own terminal once it's idle.":
        "Enter na relaci jí pošle prompt — napíše se do jejího terminálu, jakmile bude nečinná.",
    "Live Claude Code sessions on this machine": "Živé relace Claude Code na tomto počítači",
    "Kind": "Druh",
    "Directory": "Složka",
    "Delivered by typing into that session's own terminal once it's idle "
    "and not rate-limited — the response appears there, not in ccc. "
    "If you're mid-typing something else in that terminal at the exact "
    "moment this fires, the two can interleave.":
        "Doručí se napsáním do terminálu té relace, jakmile bude nečinná a mimo limit — "
        "odpověď se objeví tam, ne v ccc. Pokud zrovna v tu chvíli v tom terminálu "
        "něco píšeš, texty se můžou promíchat.",
    "Send prompt to live session": "Poslat prompt živé relaci",

    # --- Analytics ----------------------------------------------------------------
    "Claude Pro usage: unavailable (offline, or not logged in via claude.ai OAuth)":
        "Využití Claude Pro: nedostupné (offline, nebo nepřihlášeno přes claude.ai OAuth)",
    "5-hour": "5hodinový",
    "Weekly (all models)": "Týdenní (všechny modely)",
    "Weekly · {model}": "Týdenní · {model}",
    "Prev month": "Předchozí měsíc",
    "Next month": "Další měsíc",
    "Claude Pro usage (account limits)": "Využití Claude Pro (limity účtu)",
    "Tokens per day": "Tokeny po dnech",
    "Tokens by model": "Tokeny podle modelu",
    "Tokens per conversation": "Tokeny podle konverzace",
    "Rate-limited": "Limit",
    "Total time blocked on rate limits: [b]{minutes} min[/b]": "Celkový čas zablokovaný limity: [b]{minutes} min[/b]",
    "resets {time}": "obnoví se {time}",
    "Your reserve: queued tasks wait while a window is at or above {reserve}%  (change in Settings, Ctrl+P)":
        "Tvoje rezerva: úkoly ve frontě čekají, dokud je okno na {reserve} % a výš  (změníš v Nastavení, Ctrl+P)",
    "No usage reserve — queued tasks may use the whole limit  (set one in Settings, Ctrl+P)":
        "Bez rezervy využití — úkoly ve frontě můžou vyčerpat celý limit  (nastavíš v Nastavení, Ctrl+P)",
    "Tokens per day — {month}: {tokens} tokens  (← → month)": "Tokeny po dnech — {month}: {tokens} tokenů  (← → měsíc)",
    "Tokens by model — {month}": "Tokeny podle modelu — {month}",
    "Tokens per conversation — {month}": "Tokeny podle konverzace — {month}",
    "No tokens recorded in this month.": "V tomto měsíci nejsou zaznamenané žádné tokeny.",

    # --- Settings -------------------------------------------------------------------
    "Key": "Klávesa",
    "Mode": "Režim",
    "Appearance": "Vzhled",
    "Language": "Jazyk",
    "Auto (system)": "Automaticky (systém)",
    "Auto follows the system language (LANG). Saving another one restarts ccc's window.":
        "Automaticky se řídí jazykem systému (LANG). Uložení jiného jazyka restartuje okno ccc.",
    "Theme": "Motiv",
    "Applied right away so you can see it; kept after Save.": "Projeví se hned, ať ho vidíš; zůstane po Uložit.",
    "Telegram notifications": "Notifikace přes Telegram",
    "Bot token": "Token bota",
    "saved — type a new one to replace it": "uložen — napiš nový, pokud ho chceš nahradit",
    "123456:ABC… from @BotFather": "123456:ABC… od @BotFather",
    "Chat ID": "ID chatu",
    "e.g. 123456789": "např. 123456789",
    "Create a bot with @BotFather, send it any message, then open\n"
    "api.telegram.org/bot<TOKEN>/getUpdates — the chat id is under \"chat\": {\"id\": …}.\n"
    "You get a message when a queue finishes, needs you, fails or hits a usage limit.":
        "Založ bota přes @BotFather, pošli mu libovolnou zprávu a otevři\n"
        "api.telegram.org/bot<TOKEN>/getUpdates — ID chatu je u \"chat\": {\"id\": …}.\n"
        "Zprávu dostaneš, když fronta doběhne, potřebuje tě, selže nebo narazí na limit.",
    "Send test message": "Poslat testovací zprávu",
    "Turn off": "Vypnout",
    "Discord notifications": "Notifikace přes Discord",
    "Webhook URL": "URL webhooku",
    "saved — paste a new one to replace it": "uložena — vlož novou, pokud ji chceš nahradit",
    "In Discord: channel settings → Integrations → Webhooks →\n"
    "New Webhook → Copy Webhook URL. Same messages as Telegram;\n"
    "use either or both. Keep the URL private — anyone who has it\n"
    "can post to the channel.":
        "V Discordu: nastavení kanálu → Integrace → Webhooky →\n"
        "Nový webhook → Kopírovat URL webhooku. Stejné zprávy jako Telegram;\n"
        "použij jedno, nebo obojí. URL nikomu nedávej — kdo ji má,\n"
        "může do kanálu psát.",
    "Continue text": "Text pro pokračování",
    "Sent by auto-continue when a conversation stopped at a usage limit.":
        "Pošle se při automatickém pokračování, když se konverzace zastavila na limitu.",
    "Usage reserve": "Rezerva využití",
    "Queued tasks wait while a usage window (5 h / weekly) is at or above this.":
        "Úkoly ve frontě čekají, dokud je okno využití (5 h / týden) na této hodnotě a výš.",
    "Preset prompts": "Přednastavené prompty",
    "Alt+1 … Alt+9 in a conversation: ⏎ send sends it right away, ✎ insert only puts it "
    "into the message box at the cursor. Shown in the bar under the message box.":
        "Alt+1 … Alt+9 v konverzaci: ⏎ odeslat ho pošle hned, ✎ vložit ho jen vloží "
        "do pole pro zprávu na místo kurzoru. Zobrazují se v liště pod polem pro zprávu.",
    "no preset prompts yet — Add one": "zatím žádné přednastavené prompty — přidej nějaký",
    "Up": "Nahoru",
    "Down": "Dolů",
    "New-conversation presets": "Předvolby nové konverzace",
    "no presets saved": "žádné uložené předvolby",
    "choose…": "vyber…",
    "Presets are saved in the New conversation window (n → Save as preset).":
        "Předvolby se ukládají v okně Nová konverzace (n → Uložit jako předvolbu).",
    "Delete preset": "Smazat předvolbu",
    "Exports": "Exporty",
    "Export folder": "Složka pro exporty",
    "empty = {folder}": "prázdné = {folder}",
    "Exported conversations (e) go to conversations/, screenshots (Ctrl+T) to screenshots/\n"
    "inside it. Empty = ccc in your documents folder (~/ccc-exports where there is none).":
        "Exportované konverzace (e) jdou do podsložky conversations/, snímky obrazovky (Ctrl+T)\n"
        "do screenshots/. Prázdné = ccc ve složce dokumentů (kde není, tak ~/ccc-exports).",
    "After export": "Po exportu",
    "Only save to the folder": "Jen uložit do složky",
    "Also send to Telegram": "Poslat i na Telegram",
    "Also send to Discord": "Poslat i na Discord",
    "Also send to Telegram and Discord": "Poslat i na Telegram a Discord",
    "Sending puts the file on your phone when ccc runs elsewhere (server, tmux over SSH).\n"
    "Uses the Telegram / Discord set up above.":
        "Odeslání dostane soubor do telefonu, když ccc běží jinde (server, tmux přes SSH).\n"
        "Použije Telegram / Discord nastavený výše.",
    "Monthly analytics archive": "Měsíční archiv analytiky",
    "empty = off, e.g. ~/Documents/ccc_analytics": "prázdné = vypnuto, např. ~/Dokumenty/ccc_analytics",
    "The current month is here in Analytics (v). When a month ends, ccc archives it into this\n"
    "folder as Markdown notes for Obsidian (no plugins): ccc_analytics.md with all months, one\n"
    "note per month with a calendar and charts, one per day. Empty = no archive.":
        "Aktuální měsíc je tady v Analytice (v). Když měsíc skončí, ccc ho uloží do této složky\n"
        "jako Markdown poznámky pro Obsidian (bez pluginů): ccc_analytics.md se všemi měsíci,\n"
        "poznámku za měsíc s kalendářem a grafy a jednu za každý den. Prázdné = bez archivu.",
    "Archive finished months now": "Archivovat skončené měsíce hned",
    "Data": "Data",
    "Backed up automatically every day; the newest 14 copies are kept.":
        "Záloha se dělá automaticky každý den; ponechá se 14 nejnovějších.",
    "Back up now": "Zálohovat hned",
    "Settings saved.": "Nastavení uloženo.",
    "The language changes when you start ccc again.": "Jazyk se změní po dalším spuštění ccc.",
    "● on": "● zapnuto",
    "○ off — fill in the bot token and chat id": "○ vypnuto — vyplň token bota a ID chatu",
    "○ off — paste a channel webhook URL": "○ vypnuto — vlož URL webhooku kanálu",
    "Database  ": "Databáze  ",
    "Backups   ": "Zálohy    ",
    "  (last: {date})": "  (poslední: {date})",
    "Preset prompt Alt+{n}": "Přednastavený prompt Alt+{n}",
    "Fill in the bot token and chat id first.": "Nejdřív vyplň token bota a ID chatu.",
    "✓ Sent — check Telegram.": "✓ Odesláno — mrkni do Telegramu.",
    "✖ Sending failed ({error}) — check the token and chat id.":
        "✖ Odeslání selhalo ({error}) — zkontroluj token a ID chatu.",
    "Paste a Discord webhook URL (https://discord.com/api/webhooks/…) first.":
        "Nejdřív vlož URL webhooku Discordu (https://discord.com/api/webhooks/…).",
    "✓ Sent — check the Discord channel.": "✓ Odesláno — mrkni do kanálu na Discordu.",
    "✖ Sending failed ({error}) — check the webhook URL.": "✖ Odeslání selhalo ({error}) — zkontroluj URL webhooku.",
    "Choose a preset first.": "Nejdřív vyber předvolbu.",
    "Preset “{name}” deleted.": "Předvolba „{name}“ smazána.",
    "Fill in a folder first.": "Nejdřív vyplň složku.",
    "✖ Archiving failed: {error}": "✖ Archivace selhala: {error}",
    "nothing new to archive": "nic nového k archivaci",
    "Backup failed: {error}": "Záloha selhala: {error}",
    "Backed up": "Zálohováno",
    "That isn't a Discord webhook URL (https://discord.com/api/webhooks/…).":
        "Tohle není URL webhooku Discordu (https://discord.com/api/webhooks/…).",
    "Not saved": "Neuloženo",
    "✅ ccc: Telegram notifications work.": "✅ ccc: notifikace přes Telegram fungují.",
    "✅ ccc: Discord notifications work.": "✅ ccc: notifikace přes Discord fungují.",

    # --- Help window and key list (tui/help.py) -------------------------------
    "Help  ·  ↑↓ topic  ·  Tab text / topics  ·  Esc close": "Nápověda  ·  ↑↓ téma  ·  Tab text / témata  ·  Esc zavřít",
    "Keyboard shortcuts": "Klávesové zkratky",
    "Keys without Ctrl or Alt don't work while you're typing in a text field;\n"
    "Ctrl and Alt keys work everywhere. The bar at the bottom of the window\n"
    "lists the keys of the screen you're on — click one to press it.":
        "Klávesy bez Ctrl nebo Alt nefungují, když píšeš do textového pole;\n"
        "klávesy s Ctrl a Alt fungují všude. Lišta dole v okně ukazuje\n"
        "klávesy obrazovky, na které jsi — kliknutím klávesu stiskneš.",
    "Everywhere": "Všude",
    "Archive (archived conversations)": "Archiv (archivované konverzace)",
    "This help": "Tato nápověda",
    "Settings (language, theme, Telegram, queues, presets, backup)":
        "Nastavení (jazyk, motiv, Telegram, fronty, předvolby, záloha)",
    "Close ccc (it keeps running; `ccc` opens it again)": "Zavřít ccc (běží dál; `ccc` ho zase otevře)",
    "Back / close": "Zpět / zavřít",
    "Open the queue detail": "Otevřít detail fronty",
    "Close ccc (same as Ctrl+Q)": "Zavřít ccc (stejně jako Ctrl+Q)",
    "Send the selected session a prompt": "Poslat vybrané relaci prompt",
    "Reload the session list": "Znovu načíst seznam relací",
    "Add a prompt to a project's queue": "Přidat prompt do fronty projektu",
    "Open the conversation's Claude Code CLI (in the list) / send the message (in the box)":
        "Otevřít Claude Code CLI konverzace (v seznamu) / odeslat zprávu (v poli)",
    "Blocked: run the failed task again / resume one paused at a limit":
        "Zablokovaná: znovu spustit selhaný úkol / pokračovat po pauze na limitu",
    "Tasks editor (queue, schedule, pause, auto-continue)":
        "Editor úkolů (fronta, plánování, pauza, automatické pokračování)",
    "Approve a tool call Claude is waiting on": "Schválit nástroj, na který Claude čeká",
    "Archive (moves it to Archive, h)": "Archivovat (přesune do Archivu, h)",
    "Switch between ccc and Claude Code (while it's open beside ccc)":
        "Přepnout mezi ccc a Claude Code (když je otevřený vedle ccc)",
    "Close Claude Code beside ccc (it keeps running; Enter in the list opens it)":
        "Zavřít Claude Code vedle ccc (běží dál; Enter v seznamu ho otevře)",
    "Search all conversations": "Hledat ve všech konverzacích",
    "Export the conversation as Markdown": "Exportovat konverzaci jako Markdown",
    "New line in the message box (Shift+Enter where supported)": "Nový řádek v poli pro zprávu (Shift+Enter, kde funguje)",
    "Preset prompt 1–9 (⏎ sends it, ✎ puts it into the message box; set in Settings)":
        "Přednastavený prompt 1–9 (⏎ odešle, ✎ vloží do pole pro zprávu; nastavíš v Nastavení)",
    "Preset prompt 2": "Přednastavený prompt 2",
    "Preset prompt 3": "Přednastavený prompt 3",
    "Preset prompt 4": "Přednastavený prompt 4",
    "Preset prompt 5": "Přednastavený prompt 5",
    "Preset prompt 6": "Přednastavený prompt 6",
    "Preset prompt 7": "Přednastavený prompt 7",
    "Preset prompt 8": "Přednastavený prompt 8",
    "Preset prompt 9": "Přednastavený prompt 9",
    "Restore the conversation": "Obnovit konverzaci",
    "Restore it and open it in Conversations": "Obnovit ji a otevřít v Konverzacích",
    "Delete the conversation from ccc (asks first; Claude Code's transcript stays)":
        "Smazat konverzaci z ccc (nejdřív se zeptá; přepis Claude Code zůstane)",
    "Tasks editor (t)": "Editor úkolů (t)",
    "Add a task": "Přidat úkol",
    "Edit the task (also Enter)": "Upravit úkol (také Enter)",
    "Remove the task": "Odebrat úkol",
    "Pause / resume the queue": "Pozastavit / obnovit frontu",
    "Toggle auto-continue": "Zapnout / vypnout automatické pokračování",
    "Save in the task editor": "Uložit v editoru úkolu",
    "Approval window (p)": "Okno schválení (p)",
    "Always allow this tool in this conversation": "Vždy povolit tento nástroj v této konverzaci",
    "Previous calendar month": "Předchozí kalendářní měsíc",
    "Next calendar month": "Další kalendářní měsíc",
    "Show the run's commit diff": "Ukázat diff commitu z běhu",
    "Add a prompt (this queue's path prefilled)": "Přidat prompt (s předvyplněnou cestou této fronty)",
    "Preset prompt editor (Settings → Add / Edit)": "Editor přednastaveného promptu (Nastavení → Přidat / Upravit)",
    "Settings (Ctrl+P)": "Nastavení (Ctrl+P)",
    "Cancel (the theme goes back too)": "Zrušit (vrátí se i motiv)",

    # --- Guide (help/__init__.py) ------------------------------------------------
    "ccc help": "Nápověda ccc",
    "The user guide of ccc. Inside ccc press `?` — the same pages, opened on\n"
    "the screen you're on.":
        "Uživatelská příručka ccc. V ccc stiskni `?` — stejné stránky, otevřené\n"
        "na obrazovce, kde právě jsi.",
    "Starting a conversation": "Zahájení konverzace",
    "Task queue": "Fronta úkolů",
    "Usage limits & blocked queues": "Limity využití a zablokované fronty",
    "Approving tool calls": "Schvalování nástrojů",
    "Remote control (phone)": "Vzdálené ovládání (telefon)",
    "Settings & notifications": "Nastavení a notifikace",
    "Git: auto-commit & diffs": "Git: automatické commity a diffy",
    "Command line": "Příkazová řádka",
    "Troubleshooting & how it works": "Řešení potíží a jak to funguje",

    # --- daemon: notifications, run notes (orchestrator.py, …) ---------------
    "'{path}' is not an existing directory": "'{path}' není existující složka",
    "Enter a pull request number or URL.": "Zadej číslo nebo URL pull requestu.",
    "There is no previous conversation in this directory.": "V této složce není žádná předchozí konverzace.",
    "Select a conversation to resume.": "Vyber konverzaci, kterou chceš obnovit.",
    "▶ {name}: usage limit reset — continuing.": "▶ {name}: limit využití se obnovil — pokračuju.",
    "‖ {name}: usage above your {reserve}% reserve — waiting until {time}.":
        "‖ {name}: využití je nad tvou rezervou {reserve} % — čekám do {time}.",
    "⏸ {name}: usage limit — waiting until {time}, then it continues by itself.":
        "⏸ {name}: limit využití — čekám do {time}, pak se pokračuje samo.",
    "✋ {name} needs you: paused at the usage limit (resets {time}). "
    "Press r or send a message in ccc to continue.":
        "✋ {name} tě potřebuje: pozastaveno na limitu využití (obnoví se v {time}). "
        "Pro pokračování stiskni r nebo pošli zprávu v ccc.",
    "not committed: auto-commit only runs in 'Skip all permission checks' conversations":
        "necommitnuto: automatický commit běží jen v konverzacích s 'Přeskočit všechny kontroly oprávnění'",
    "✅ {name}: queue finished.": "✅ {name}: fronta doběhla.",
    "session is no longer running (closed or crashed)": "relace už neběží (zavřená nebo spadla)",
    "delivery to live terminal failed": "doručení do živého terminálu selhalo",
    "Delivered to the live terminal — response appears there, not in ccc.":
        "Doručeno do živého terminálu — odpověď se objeví tam, ne v ccc.",
    "delivery to the interactive session failed": "doručení do interaktivní relace selhalo",
    "Delivered to the interactive session — the reply is in the transcript.":
        "Doručeno do interaktivní relace — odpověď je v přepisu.",
    "session {session} already has a conversation in ccc": "relace {session} už v ccc konverzaci má",
    "✖ {name}: stopped on an error — {error}": "✖ {name}: zastaveno chybou — {error}",
    "unknown error": "neznámá chyba",
    "queue {id}": "fronta {id}",
    "✋ {name} needs you: Claude wants to use {tool} — {preview}\n"
    "Open the conversation in ccc and press p.":
        "✋ {name} tě potřebuje: Claude chce použít {tool} — {preview}\n"
        "Otevři konverzaci v ccc a stiskni p.",
    "session is no longer running": "relace už neběží",
    "session is not ready for input": "relace není připravená na vstup",
    "session has no known process id": "relace nemá známé ID procesu",
    "could not find a tmux pane for this session": "pro tuto relaci se nenašel panel tmuxu",
    # git notes (gitops.py)
    "couldn't read the repo's git config": "nepodařilo se přečíst git config repozitáře",
    "repo git config has '{key}', which ccc doesn't run git with":
        "git config repozitáře obsahuje '{key}', se kterým ccc git nespouští",
    "not committed: {reason}": "necommitnuto: {reason}",
    "not committed: the repo's git config changed during the task":
        "necommitnuto: git config repozitáře se během úkolu změnil",
    "not committed: there were uncommitted changes before the task":
        "necommitnuto: před úkolem tu byly necommitnuté změny",
    "not committed: detached HEAD": "necommitnuto: odpojený HEAD",
    "not committed: git status failed": "necommitnuto: git status selhal",
    "no changes": "žádné změny",
    "not committed: git commit failed": "necommitnuto: git commit selhal",
    "committed": "commitnuto",
    "Not shown: {reason}.": "Nezobrazeno: {reason}.",
    "… (truncated, {n} chars)": "… (zkráceno, celkem znaků: {n})",
    "… (truncated, {n} chars total)": "… (zkráceno, celkem znaků: {n})",
    # task times (schedule.py)
    "Usage data isn't available, so the next reset time is unknown.":
        "Data o využití nejsou k dispozici, takže čas dalšího obnovení není známý.",
    "'{text}' isn't a valid time.": "'{text}' není platný čas.",
    "Use HH:MM, YYYY-MM-DD HH:MM or 'reset' — not '{text}'.": "Použij HH:MM, RRRR-MM-DD HH:MM nebo 'reset' — ne '{text}'.",
    # preset prompts typed into Claude Code (cli_input.py)
    "Not an interactive conversation.": "Není to interaktivní konverzace.",
    "Claude Code isn't running for this conversation yet.": "Claude Code pro tuto konverzaci ještě neběží.",
    "Couldn't type it into Claude Code.": "Do Claude Code se to nepodařilo napsat.",
    # attach_cli.py
    "Starting Claude Code… (the ccc daemon starts it)": "Spouštím Claude Code… (spouští ho daemon ccc)",
    "Still waiting — is the ccc daemon running? (systemctl --user status ccc)":
        "Pořád čekám — běží daemon ccc? (systemctl --user status ccc)",

    # --- monthly archive notes (analytics_archive.py) ---------------------------
    "ccc analytics": "Analytika ccc",
    "**{tokens} tokens in archived months** — headless runs and remote-control conversations "
    "started through ccc. A month is archived here when it ends; the current month is in ccc → "
    "Analytics (`v`). Generated by ccc.":
        "**{tokens} tokenů v archivovaných měsících** — běhy na pozadí a konverzace se vzdáleným ovládáním "
        "spuštěné přes ccc. Měsíc se sem archivuje, když skončí; aktuální měsíc je v ccc → "
        "Analytika (`v`). Vygenerováno ccc.",
    "(nothing archived yet)": "(zatím nic archivováno)",
    "Tokens per month": "Tokeny po měsících",
    "Tokens per day — {month}": "Tokeny po dnech — {month}",
    "Million tokens": "Miliony tokenů",
    "By model": "Podle modelu",
    "By conversation": "Podle konverzace",
    "**{tokens} tokens**": "**{tokens} tokenů**",
    "All months": "Všechny měsíce",

    # --- ccc command line (cli.py) ------------------------------------------------
    "Queue a prompt for a project without opening the TUI (needs ccc-daemon running to actually execute it)":
        "Zařadit prompt do fronty projektu bez otevření TUI (ke spuštění musí běžet ccc-daemon)",
    "Run the TUI itself (what the ccc-tui service runs; plain `ccc` attaches to it)":
        "Spustit samotné TUI (to spouští služba ccc-tui; obyčejné `ccc` se k němu připojí)",
    "Type preset prompt N into an interactive conversation's Claude Code (Alt+N in its pane)":
        "Napsat přednastavený prompt N do Claude Code interaktivní konverzace (Alt+N v jejím panelu)",
    "ccc database (default: the usual one)": "databáze ccc (výchozí: ta obvyklá)",
    "tmux client to show an error on": "klient tmuxu, kde ukázat chybu",
    "that client's tmux server socket": "socket tmux serveru toho klienta",
    "Back up the ccc database now (the daemon also does it daily)": "Zálohovat databázi ccc hned (daemon to dělá i denně)",
    "Archive finished months into the analytics folder now (the daemon does it hourly)":
        "Archivovat skončené měsíce do složky analytiky hned (daemon to dělá každou hodinu)",
    "Show or change ccc settings": "Ukázat nebo změnit nastavení ccc",
    "Message sent after a usage limit interrupted a prompt mid-way (no value: show it)":
        "Zpráva poslaná poté, co limit využití přerušil rozpracovaný prompt (bez hodnoty: ukáže ji)",
    "Telegram bot token for notifications (no value: show it masked)":
        "Token Telegram bota pro notifikace (bez hodnoty: ukáže ho zamaskovaný)",
    "Telegram chat id to notify (no value: show it)": "ID Telegram chatu pro notifikace (bez hodnoty: ukáže ho)",
    "Don't start queued tasks above this %% of a usage window (1-99, or off)":
        "Nespouštět úkoly z fronty nad tímto %% okna využití (1-99, nebo off)",
    "Send a test notification": "Poslat testovací notifikaci",
    "Discord channel webhook URL for notifications (no value: show it masked; off: remove)":
        "URL webhooku kanálu Discordu pro notifikace (bez hodnoty: ukáže ji zamaskovanou; off: odebere)",
    "Folder for the monthly analytics archive (no value: show it; off: stop archiving)":
        "Složka pro měsíční archiv analytiky (bez hodnoty: ukáže ji; off: vypne archivaci)",
    "Send a test notification to Discord": "Poslat testovací notifikaci na Discord",
    "Language of ccc: auto (system), en or cs (no value: show it)":
        "Jazyk ccc: auto (systém), en nebo cs (bez hodnoty: ukáže ho)",
    "{setting} (now: {language})": "{setting} (teď: {language})",
    "ccc: language takes auto, en or cs": "ccc: language bere auto, en nebo cs",
    "language set to {language}. Restart ccc (Ctrl+Q) to see it in the TUI.":
        "jazyk nastaven na {language}. V TUI se projeví po restartu ccc (Ctrl+Q).",
    "ccc: set `ccc config telegram-token …` and `ccc config telegram-chat …` first":
        "ccc: nejdřív nastav `ccc config telegram-token …` a `ccc config telegram-chat …`",
    "Test message sent.": "Testovací zpráva odeslána.",
    "ccc: sending failed — check the token and chat id": "ccc: odeslání selhalo — zkontroluj token a ID chatu",
    "(off)": "(vypnuto)",
    "analytics-folder removed: monthly archive off.": "analytics-folder odebrána: měsíční archiv je vypnutý.",
    "analytics-folder set to {folder} — finished months are archived there.":
        "analytics-folder nastavena na {folder} — skončené měsíce se archivují tam.",
    "ccc: set `ccc config discord-webhook …` first": "ccc: nejdřív nastav `ccc config discord-webhook …`",
    "ccc: sending failed — check the webhook URL": "ccc: odeslání selhalo — zkontroluj URL webhooku",
    "(not set)": "(nenastaveno)",
    "discord-webhook removed.": "discord-webhook odebrán.",
    "ccc: that isn't a Discord webhook URL (https://discord.com/api/webhooks/…)":
        "ccc: tohle není URL webhooku Discordu (https://discord.com/api/webhooks/…)",
    "discord-webhook saved.": "discord-webhook uložen.",
    "{setting} saved.": "{setting} uloženo.",
    "usage-reserve off.": "usage-reserve vypnuta.",
    "ccc: usage-reserve takes a number from 1 to 99, or off": "ccc: usage-reserve bere číslo od 1 do 99, nebo off",
    "usage-reserve set to {percent}%: queued tasks wait while a usage window is at or above it.":
        "usage-reserve nastavena na {percent} %: úkoly ve frontě čekají, dokud je okno využití na ní a výš.",
    "continue-text set to: {text}": "continue-text nastaven na: {text}",
    "ccc: set `ccc config analytics-folder PATH` first": "ccc: nejdřív nastav `ccc config analytics-folder CESTA`",
    "nothing new": "nic nového",
    "Archived: {months} ({folder})": "Archivováno: {months} ({folder})",
    "Backed up to {path}": "Zálohováno do {path}",
}
