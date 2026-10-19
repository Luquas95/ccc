"""python -m ccc.help — rewrite the generated pages (README.md, keys.md
and their Czech twins in cs/) after changing TOPICS or the key list
(tui.help.KEY_HELP)."""
from pathlib import Path

from ccc import i18n
from ccc.help import index_markdown
from ccc.tui.help import keys_markdown

here = Path(__file__).parent
for code, folder in (("en", here), ("cs", here / "cs")):
    i18n.set_language(code)
    folder.mkdir(exist_ok=True)
    (folder / "README.md").write_text(index_markdown(), encoding="utf-8")
    (folder / "keys.md").write_text(keys_markdown(), encoding="utf-8")
