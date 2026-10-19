"""python -m ccc.help — rewrite the generated pages (README.md, keys.md)
after changing TOPICS or the key list (tui.help.KEY_HELP)."""
from pathlib import Path

from ccc.help import index_markdown
from ccc.tui.help import keys_markdown

here = Path(__file__).parent
(here / "README.md").write_text(index_markdown(), encoding="utf-8")
(here / "keys.md").write_text(keys_markdown(), encoding="utf-8")
