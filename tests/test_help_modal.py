"""Pilot tests for the Help modal."""

from unittest.mock import MagicMock

import pytest

from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.tui.modals.help import HelpModal


def _app() -> YTMusicApp:
    search = MagicMock()
    search.suggest = MagicMock(return_value=[])
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    return YTMusicApp(search_service=search, playback_service=playback)


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
