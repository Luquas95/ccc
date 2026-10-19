from ccc.tui.pixel_text import ROWS, layout, render_word


def test_word_is_five_rows_of_pixels():
    lines = render_word("NO")
    assert len(lines) == ROWS
    assert lines[0] == "█   █  ███ "
    assert len({len(line) for line in lines}) == 1


def test_every_banner_text_has_glyphs():
    from ccc.tui.archive import ArchiveScreen
    from ccc.tui.conversations import ConversationsScreen

    for screen in (ConversationsScreen, ArchiveScreen):
        assert len(render_word(screen.BANNER_TEXT)) == ROWS


def test_layout_fits_the_width():
    wide = layout("NO CONVERSATION", 200)
    assert len(wide) == ROWS and max(map(len, wide)) <= 200
    narrow = layout("NO CONVERSATION", 75)  # phone: one band per word
    assert len(narrow) == 2 * ROWS + 1 and max(map(len, narrow)) <= 75
    assert layout("NO CONVERSATION", 30) == ["NO CONVERSATION"]


def test_czech_banners_have_their_letters():
    from ccc.tui.pixel_text import GLYPHS

    for banner in ("BEZ KONVERZACE", "PRÁZDNO"):
        assert set(banner) <= set(GLYPHS)
        assert len(render_word(banner)) == ROWS


def test_a_letter_without_a_glyph_loses_its_accent():
    assert render_word("Č") == render_word("C")
