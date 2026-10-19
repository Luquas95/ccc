# Živé relace

Živé relace (`s`) ukazují **všechny relace Claude Code běžící na tomto
počítači** — i ty, které sis spustil(a) sám/sama v terminálu mimo ccc —
s jejich stavem a složkou.

![Živé relace](../../../../docs/screenshots/sessions.png)

| Klávesa | |
|---|---|
| `Enter` | pošle vybrané relaci prompt |
| `r` | znovu načte seznam |
| `a` | přidá prompt do fronty libovolného projektu (běží [na pozadí](conversations.md)) |

## Poslání promptu běžící relaci

`Enter` na relaci jí zařadí prompt. ccc počká, až bude ten Claude
nečinný, a pak prompt napíše do jeho terminálu — uvidíš, jak tam
pokračuje. Odpověď se objeví v tom terminálu, ne v ccc.

Pozor na terminál, do kterého sám/sama píšeš: ccc pozná, že je nečinný
*Claude*, ne že *ty* zrovna něco píšeš, takže by se texty mohly
promíchat. Pro práci, kterou chceš předat ccc, je lepší konverzace
založená přes `n`.

Relace z terminálu se objeví na Přehledu a v Konverzacích ccc, jakmile
jí takhle pošleš prompt.
