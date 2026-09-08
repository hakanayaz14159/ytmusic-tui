"""Pilot tests for the Help modal."""

from unittest.mock import MagicMock

import pytest

from tests.conftest import make_test_app
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.tui.modals.help import HelpModal, HelpScroll


def _app() -> YTMusicApp:
    search = MagicMock()
    search.suggest = MagicMock(return_value=[])
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    return make_test_app(search_service=search, playback_service=playback)


@pytest.mark.asyncio
async def test_help_modal_dismisses_on_q() -> None:
    app = _app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        help_open = isinstance(app.screen, HelpModal)
        assert help_open is True
        await pilot.press("q")
        await pilot.pause()
        help_open = isinstance(app.screen, HelpModal)
        assert help_open is False
        assert app.is_running


@pytest.mark.asyncio
async def test_help_lists_suggestion_keys() -> None:
    app = _app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        help_text = str(app.screen.query_one("Static").render())
        lowered = help_text.lower()
        assert "down" in lowered
        assert "complete" in lowered
        assert "shift+tab" in lowered
        assert "=" in help_text
        assert "←" in help_text or "h" in lowered
        assert "first item" in lowered
        assert "last item" in lowered
        assert "half-page" in lowered
        assert "shift+h" in lowered
        assert "shift+l" in lowered
        assert "append to queue" in lowered
        assert "<  z" in help_text
        assert "z  x" in help_text
        assert "iso" in lowered
        assert "which pair is active" in lowered
        assert "seek" in lowered
        assert "-5s" in lowered
        assert "+5s" in lowered


@pytest.mark.asyncio
async def test_help_can_scroll_to_all_keys_on_small_terminal() -> None:
    app = _app()
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(HelpModal())
        await pilot.pause()
        panel = app.screen.query_one("#help_panel", HelpScroll)
        panel.scroll_end(animate=False)
        await pilot.pause()
        assert panel.scroll_y > 0


@pytest.mark.asyncio
async def test_help_scrolls_with_vim_keys() -> None:
    app = _app()
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(HelpModal())
        await pilot.pause()
        panel = app.screen.query_one("#help_panel", HelpScroll)
        await pilot.pause()
        assert panel.scroll_y == 0

        await pilot.press("j")
        await pilot.pause()
        after_j = panel.scroll_y
        assert after_j > 0

        await pilot.press("k")
        await pilot.pause()
        assert panel.scroll_y < after_j

        await pilot.press("G")
        await pilot.pause()
        at_end = panel.scroll_y
        assert at_end > 0

        await pilot.press("g")
        await pilot.pause()
        assert panel.scroll_y < at_end
