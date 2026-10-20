"""The user guide (ccc.help), English and Czech (cs/): every page there,
links and images work, generated pages up to date."""
import re
from pathlib import Path

import pytest

from ccc import help as guide
from ccc import i18n
from ccc.tui.help import keys_markdown

HELP_DIR = Path(guide.__file__).parent
LANGUAGE_DIRS = {"en": HELP_DIR, "cs": HELP_DIR / "cs"}
LINK = re.compile(r"\]\(([^)\s]+)\)")


@pytest.fixture
def language():
    yield i18n.set_language
    i18n.set_language("en")


@pytest.mark.parametrize("folder", LANGUAGE_DIRS.values(), ids=LANGUAGE_DIRS.keys())
def test_every_topic_has_a_page_and_every_page_is_a_topic(folder):
    pages = {p.stem for p in folder.glob("*.md")} - {"README"}
    assert pages == {slug for slug, _ in guide.TOPICS}


@pytest.mark.parametrize("code", LANGUAGE_DIRS)
def test_generated_pages_are_up_to_date(code, language):
    # Out of date? Run: .venv/bin/python -m ccc.help
    language(code)
    assert (LANGUAGE_DIRS[code] / "README.md").read_text() == guide.index_markdown()
    assert (LANGUAGE_DIRS[code] / "keys.md").read_text() == keys_markdown()


def test_czech_pages_follow_the_english_ones():
    """Same sections and screenshots in the same order: a translation
    that fell behind its English page shows here."""
    for page in sorted(HELP_DIR.glob("*.md")):
        czech = (HELP_DIR / "cs" / page.name).read_text()
        english = page.read_text()
        for pattern in (r"^#+ ", r"!\[[^\]]*\]\(([^)]+)\)", r"\]\(([\w-]+\.md)"):
            assert len(re.findall(pattern, czech, re.M)) == len(re.findall(pattern, english, re.M)), (page.name, pattern)
        assert re.findall(r"!\[[^\]]*\]\(([^)]+)\)", czech) == [
            "../" + target for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", english)], page.name


def test_read_picks_the_language(language):
    language("cs")
    assert guide.read("tasks") == (HELP_DIR / "cs" / "tasks.md").read_text()
    assert guide.title("tasks") == "Fronta úkolů"
    language("en")
    assert guide.read("tasks") == (HELP_DIR / "tasks.md").read_text()


@pytest.mark.parametrize("page", sorted(HELP_DIR.glob("*.md")) + sorted((HELP_DIR / "cs").glob("*.md")),
                         ids=lambda p: p.relative_to(HELP_DIR).as_posix())
def test_links_and_images_point_somewhere(page):
    for target in LINK.findall(page.read_text()):
        if target.startswith(("http://", "https://")):
            continue
        assert (page.parent / target.split("#")[0]).resolve().exists(), f"{page.name}: {target}"


def test_every_view_opens_on_a_topic():
    from ccc.tui.layout import VIEWS

    assert {view for view, _ in VIEWS} == set(guide.VIEW_TOPICS)
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
