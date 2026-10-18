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
