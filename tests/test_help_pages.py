"""The user guide (ccc.help): every page there, links and images work,
generated pages up to date."""
import re
from pathlib import Path

import pytest

from ccc import help as guide
from ccc.tui.help import keys_markdown

HELP_DIR = Path(guide.__file__).parent
LINK = re.compile(r"\]\(([^)\s]+)\)")


def test_every_topic_has_a_page_and_every_page_is_a_topic():
    pages = {p.stem for p in HELP_DIR.glob("*.md")} - {"README"}
    assert pages == {slug for slug, _ in guide.TOPICS}


def test_generated_pages_are_up_to_date():
    # Out of date? Run: .venv/bin/python -m ccc.help
    assert (HELP_DIR / "README.md").read_text() == guide.index_markdown()
    assert (HELP_DIR / "keys.md").read_text() == keys_markdown()


@pytest.mark.parametrize("page", sorted(HELP_DIR.glob("*.md")), ids=lambda p: p.name)
def test_links_and_images_point_somewhere(page):
    for target in LINK.findall(page.read_text()):
        if target.startswith(("http://", "https://")):
            continue
        assert (page.parent / target.split("#")[0]).resolve().exists(), f"{page.name}: {target}"


def test_every_view_opens_on_a_topic():
    from ccc.tui.layout import VIEWS

    assert {view for view, _, _ in VIEWS} == set(guide.VIEW_TOPICS)
    assert set(guide.VIEW_TOPICS.values()) <= {slug for slug, _ in guide.TOPICS}


def test_terminal_version_drops_the_screenshots():
    text = guide.for_terminal("# T\n\n![Shot](../x.png)\n<img src=\"y.png\">\nSee [tasks](tasks.md).\n")
    assert "png" not in text and "[tasks](tasks.md)" in text


def test_readme_links_every_topic_and_its_links_work():
    readme = HELP_DIR.parents[2] / "README.md"
    text = readme.read_text()
    listed = re.findall(r"\(src/ccc/help/([\w-]+)\.md\)", text.split("## Help", 1)[1].split("\n## ", 1)[0])
    assert listed == [slug for slug, _ in guide.TOPICS]
    for target in LINK.findall(text):
        if not target.startswith(("http://", "https://")):
            assert (readme.parent / target.split("#")[0]).exists(), target
