"""The terminal widget: runs a command in a pty and draws its screen."""
import asyncio
import sys

import pytest
from textual.app import App

from ccc.tui.terminal_pane import TerminalPane, color, encode_key


class Host(App):
    def __init__(self, command):
        super().__init__()
        self.command = command
        self.events = []

    def compose(self):
        yield TerminalPane(self.command, id="term")

    def on_terminal_pane_exited(self, message):
        self.events.append(("exited", message.returncode))

    def on_terminal_pane_released(self, message):
        self.events.append(("released",))


async def wait_for(pane, text, seconds=5):
    for _ in range(int(seconds * 50)):
        if text in pane.text():
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"{text!r} not on screen:\n{pane.text()}")


def test_colours_and_keys():
    assert color("default") is None and color("brown") == "yellow"
    assert color("brightgreen") == "bright_green" and color("5fd7af") == "#5fd7af"
    assert encode_key("ctrl+c", None) == "\x03" and encode_key("up", None) == "\x1b[A"
    assert encode_key("a", "a") == "a" and encode_key("alt+x", None) == "\x1bx"
    assert encode_key("ctrl+right_square_bracket", None) is None


@pytest.mark.asyncio
async def test_output_is_drawn_with_colours():
    app = Host(["sh", "-c", r"printf '\033[31mred\033[0m plain\n\033[38;2;1;2;3mtrue\033[0m'; sleep 5"])
    async with app.run_test(size=(40, 6)) as pilot:
        pane = app.query_one(TerminalPane)
        await wait_for(pane, "red plain")
        await wait_for(pane, "true")
        await pilot.pause(0.2)
        first = pane.render_line(0)
        styles = {seg.text: seg.style for seg in first if seg.text.strip()}
        assert styles["red"].color.name == "red"
        assert pane.render_line(1).text.startswith("true")


@pytest.mark.asyncio
async def test_keys_and_paste_reach_the_command_and_it_is_resized():
    app = Host(["sh", "-c", "stty -echo; while read l; do echo \"got:$l size:$(stty size)\"; done"])
    async with app.run_test(size=(50, 8)) as pilot:
        pane = app.query_one(TerminalPane)
        pane.focus()
        await pilot.pause(0.3)
        await pilot.press("h", "i", "enter")
        await wait_for(pane, "got:hi size:8 50")
        await pilot.resize_terminal(60, 10)
        await pilot.pause(0.3)
        await pilot.press("x", "enter")
        await wait_for(pane, "got:x size:10 60")


@pytest.mark.asyncio
async def test_release_key_and_exit_are_reported():
    app = Host(["sh", "-c", "sleep 0.5"])
    async with app.run_test(size=(40, 6)) as pilot:
        pane = app.query_one(TerminalPane)
        pane.focus()
        await pilot.pause(0.2)
        await pilot.press("ctrl+right_square_bracket")
        await pilot.pause(0.2)
        assert ("released",) in app.events
        for _ in range(100):
            if any(e[0] == "exited" for e in app.events):
                break
            await asyncio.sleep(0.05)
        assert ("exited", 0) in app.events


@pytest.mark.asyncio
async def test_private_csi_sequences_do_not_change_the_text_style():
    # Claude Code sends CSI > 4;2 m at the start; pyte would turn it into underline.
    app = Host(["sh", "-c", r"printf '\033[>4;2m\033[>1ux'; printf 'ab\033'; sleep 0.2; printf '[>4;2mcd'; sleep 5"])
    async with app.run_test(size=(30, 4)) as pilot:
        pane = app.query_one(TerminalPane)
        await wait_for(pane, "abcd")
        await pilot.pause(0.1)
        assert all(seg.style.underline is None for seg in pane.render_line(0))
