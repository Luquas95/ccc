# Zahájení konverzace

Kdekoli stiskni `n` (nebo zelené tlačítko **Nová konverzace**
v Konverzacích). Okno má dvě poloviny.

![Nová konverzace](../../../../docs/screenshots/new_conversation.png)

## Složka

Složka projektu, ve které bude Claude pracovat: vyber některou
z nedávných, projdi strom složek, nebo napiš cestu.

## Volby

Stejné přepínače jako na příkazové řádce `claude`. Skupiny označené
*jedna* dovolí jen jednu volbu.

| Skupina | Volby |
|---|---|
| Relace (*jedna*) | **Nová relace** · **Pokračovat v poslední ve složce** · **Obnovit vybranou…** (vybereš některou z dřívějších relací Claude Code v této složce) · **Z pull requestu…** |
| | **Jako kopie (fork)** — s Pokračovat / Obnovit / Z PR: nová konverzace, která z té původní vychází; původní zůstane, jak byla |
| Oprávnění (*jedna*) | **Přeskočit všechny kontroly oprávnění** — Claude dělá všechno bez ptaní · **Automaticky přijímat úpravy** — úpravy souborů ano, ostatní nástroje se ptají · **Jen plán** — Claude jen plánuje |
| Model (*jedna*) | Opus · Sonnet · Haiku · Fable |
| Úsilí (*jedna*) | high · xhigh · max |
| Ostatní | Při přetížení přejít na Sonnet · Claude v Chromu · Bezpečný režim |
| | **Vlastní git worktree** — samostatná pracovní kopie a větev pro tuto konverzaci (`.claude/worktrees/<název>`, větev `worktree-<název>`), aby mohla pracovat vedle ostatních ve stejném repozitáři; jen s novou relací nebo z pull requestu. Viz [Git](git.md#více-konverzací-v-jedné-složce) |

Pod nimi:

- **Automaticky pokračovat po limitu využití** (výchozí zapnuto) — když
  Claude narazí na tvůj limit využití, konverzace počká na obnovení
  a sama pokračuje. Vypnuto: zastaví se a čeká na tebe. Viz
  [Limity využití](limits.md).
- **Vzdálené ovládání (telefon / claude.ai)** — v konverzaci můžeš
  pokračovat i z mobilní aplikace Claude. Viz
  [Vzdálené ovládání](remote-control.md).

Nic nezaškrtnuto znamená výchozí nastavení Claude Code.

## Předvolby

Okno si pamatuje tvou poslední volbu. Pokud často používáš pár
kombinací, **Uložit jako předvolbu** uloží tu aktuální pod názvem;
**Vyber předvolbu…** jí okno vyplní. Předvolby mažeš
v [Nastavení](settings.md).

## Po Spustit

Jsi v [Konverzacích](conversations.md) a vedle ccc je otevřené Claude
Code. Obnovení relace, která už v ccc konverzaci má, jen přepne na tu
konverzaci — pokud nezaškrtneš *Jako kopie (fork)*.
