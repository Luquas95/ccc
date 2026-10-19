# Řešení potíží a jak to funguje

## Postranní panel ukazuje „daemon neběží“

Bez daemonu se nic nestane. Zkontroluj ho a spusť:

```bash
systemctl --user status ccc        # běží?
systemctl --user restart ccc
journalctl --user -u ccc -f        # jeho log
```

Aby běžel i po odhlášení nebo zavření SSH, jednou zapni lingering:
`loginctl enable-linger "$USER"`.

**Šifrovaný domovský adresář (ecryptfs):** služby nemůžou naběhnout při
startu počítače, dokud se nepřihlásíš, protože jejich soubory jsou ještě
zašifrované. Spouštěj je radši po přihlášení, třeba položkou automatického
spuštění ve svém desktopu, která zavolá
`systemctl --user daemon-reload && systemctl --user start ccc.service ccc-tui.service`.

## `ccc` se neotevře / ukazuje něco divného

Stále běžící ccc má vlastní tmux server (`tmux -L ccc`), takže ho
v obyčejném `tmux ls` neuvidíš. `ccc` se k němu připojí; pokud neběží
služba `ccc-tui`, `ccc` ji spustí. Když ccc samo skončí, za vteřinu je
zpátky. `systemctl --user restart ccc-tui` ho restartuje.

## Konverzace se zastavila

`✖` = zastavená chybou, `‖` = čeká na limit využití nebo je pozastavená.
Viz [Limity využití a zablokované fronty](limits.md).

## Obnovení zálohy

1. `systemctl --user stop ccc ccc-tui`
2. Zkopíruj zálohu z `~/.local/share/ccc/backups/` přes
   `~/.local/share/ccc/history.db`.
3. `systemctl --user start ccc ccc-tui`

## Jak ccc funguje

- **`ccc-daemon`** je jediný, kdo kdy spouští Clauda. Je to služba na
  pozadí, která přežije odhlášení ze SSH, pády (restartuje se)
  i restarty počítače.
- **TUI** jen čte a zapisuje databázi ccc; nikdy nespouští prompt. Můžeš
  ho kdykoli zavřít.
- Obojí sdílí jednu databázi SQLite (`~/.local/share/ccc/history.db`);
  úkol se přebírá atomicky, takže nikdy neběží dvakrát.
- Konverzace s Claude Code vedle ccc běží jako interaktivní procesy
  `claude` ve skrytém tmux serveru (`tmux -L ccc-sessions`), které daemon
  drží naživu.
- ccc používá tvoje běžné přihlášení do Claude Code — žádný API klíč —
  a **stejné** 5hodinové / týdenní využití jako každá jiná relace Claude
  Code na počítači. Zobrazené ceny jsou ekvivalent ceníku Anthropicu, ne
  poplatek navíc.
- Limit využití se pozná podle vlastního chybového stavu Claude Code
  (429), ne hádáním z textu. Když čas obnovení není známý, ccc to zkusí
  znovu za 15, pak za 30 a pak za 60 minut.
- Jazyk (Nastavení → Vzhled, nebo `ccc config language`) platí pro TUI,
  nápovědu, notifikace, poznámky měsíčního archivu i výpisy `ccc`.
