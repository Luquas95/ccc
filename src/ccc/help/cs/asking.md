# Konverzace se ptají navzájem

Konverzace se mohou ptát jedna druhé: „zeptej se konverzace, která dělá
API, jaká pole vrací `/orders`, než změníš klienta“. Otázka přijde do
[fronty úkolů](tasks.md) druhé konverzace; jakmile odpoví, ccc odpověď
předá zpět tazatelce jako její další zprávu.

## Ptáš se ty

Klávesa `k` v [Konverzacích](conversations.md) nebo v detailu fronty:
vyber konverzaci, napiš otázku, **Odeslat** (`Ctrl+S`). Se zapnutým
**Předat odpověď do této konverzace** (výchozí) si Claude odpověď přečte
jako další zprávu; vypnuté — přečteš si ji jen ty v okně.

Okno ukazuje otázky této konverzace: `→` ptala se jiné, `←` jiná se
ptala jí, `🤖` Claude se zeptal sám. Vyber otázku a uvidíš ji i
odpověď; **Zrušit otázku** zahodí tu, která ještě čeká.

## Ptá se Claude

Každá konverzace, kterou ccc spouští, má nástroj ccc
`ask_conversation` se seznamem ostatních konverzací v popisu — stačí
Claudovi říct „zeptej se konverzace *API*, jestli …“. Otázka nikdy
nečeká: Claude pokračuje a odpověď přijde jako pozdější zpráva. Dvě
konverzace, které se ptají navzájem, se tak nezablokují, a aby se
nezacyklily:

- konverzace, která právě odpovídá na otázku, se sama ptát nemůže;
- konverzace má najednou nejvýš 3 otevřené otázky.

V konverzaci bez *Přeskočit všechny kontroly oprávnění* se Claude Code
nejdřív zeptá tebe, jako u každého nástroje.

Otázky i odpovědi jsou označené jako od jiné konverzace, ne od tebe —
informace, ne pokyny. Odpověď je odpověď konverzace na pozadí, u
interaktivní to, co Claude po otázce napsal, jakmile nic nedělá. Každá
odpověď přijde i na Telegram / Discord, pokud jsou nastavené.

Z příkazové řádky: `ccc ask OD KOMU "otázka" [--wait]` a `ccc asks`
(viz [Příkazová řádka](command-line.md)).
