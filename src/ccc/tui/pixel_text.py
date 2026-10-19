"""Big pixel letters (5 rows of █) for banners such as "NO CONVERSATION"
("BEZ KONVERZACE" in Czech) in the Conversations view."""
from __future__ import annotations

import unicodedata

from rich.text import Text
from textual.widgets import Static

ROWS = 5
# Each glyph: ROWS strings of equal width; "#" is a lit pixel.
GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (" ### ", "#   #", "#####", "#   #", "#   #"),
    "Á": ("   # ", " ### ", "#   #", "#####", "#   #"),
    "B": ("#### ", "#   #", "#### ", "#   #", "#### "),
    "C": (" ####", "#    ", "#    ", "#    ", " ####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#### ", "#    ", "#####"),
    "I": ("###", " # ", " # ", " # ", "###"),
    "K": ("#   #", "#  # ", "###  ", "#  # ", "#   #"),
    "M": ("#   #", "## ##", "# # #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#### ", "#    ", "#    "),
    "R": ("#### ", "#   #", "#### ", "#  # ", "#   #"),
    "S": (" ####", "#    ", " ### ", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  "),
    "V": ("#   #", "#   #", "#   #", " # # ", "  #  "),
    "Y": ("#   #", " # # ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "   # ", "  #  ", " #   ", "#####"),
    " ": ("   ",) * ROWS,
}


def _base_letter(char: str) -> str:
    """Č -> C: a letter without its own glyph is drawn without its accent."""
    return unicodedata.normalize("NFD", char)[0]


def render_word(word: str) -> list[str]:
    """ROWS lines of pixels for `word` (letters one column apart)."""
    glyphs = [GLYPHS.get(c) or GLYPHS.get(_base_letter(c), GLYPHS[" "]) for c in word.upper()]
    return [" ".join(g[row] for g in glyphs).replace("#", "█") for row in range(ROWS)]


def layout(text: str, width: int) -> list[str]:
    """The banner lines fitting `width`: one pixel row band, else one band
    per word, else the plain text."""
    bands = [[text]]
    if " " in text:
        bands.append(text.split())
    for words in bands:
        rendered = [render_word(w) for w in words]
        widest = max(len(line) for band in rendered for line in band)
        if widest <= width:
            lines: list[str] = []
            for band in rendered:
                if lines:
                    lines.append("")
                lines.extend(line.center(widest) for line in band)
            return lines
    return [text]


class PixelBanner(Static):
    """`text` in big pixel letters, sized to the widget's width."""

    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.banner_text = text

    def render(self) -> Text:
        return Text("\n".join(layout(self.banner_text, self.size.width)))
