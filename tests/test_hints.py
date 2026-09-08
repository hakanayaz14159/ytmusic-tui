"""Unit and pilot tests for focus-aware status hints."""

from unittest.mock import MagicMock

import pytest
from textual.widgets import Input

from tests.conftest import make_test_app
from ytmusic_tui.music.types import Song
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.tui.hints import hints_for
from ytmusic_tui.tui.widgets.song_table import SongTable, VimListView
from ytmusic_tui.tui.widgets.status_bar import StatusBar

SAMPLE_SONGS: list[Song] = [
    {
        "video_id": "hint1",
        "title": "Hint Track",
        "artist": "Hint Artist",
        "album": None,
        "duration": 90,
    }
]


def test_hints_for_search_input_omits_list_motions() -> None:
    text = hints_for("search", "input")
    assert "esc blur" in text
    assert "down/up complete" in text
    assert "g/G" not in text


def test_hints_for_search_list_includes_motions_and_reentry() -> None:
    text = hints_for("search", "list")
    assert "j/k" in text
    assert "g/G" in text
    assert "/ search" in text


def test_hints_for_other_modes_include_list_motions() -> None:
    assert "g/G" in hints_for("queue", "list")
    assert "h/l pane" in hints_for("playlists", "list")
    assert "h/l adjust" in hints_for("settings", "list")


def _app() -> YTMusicApp:
    search = MagicMock()
    search.search = MagicMock(return_value=SAMPLE_SONGS)
    search.suggest = MagicMock(return_value=[])
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    return make_test_app(search_service=search, playback_service=playback)


@pytest.mark.asyncio
async def test_status_bar_uses_input_hints_on_search_landing() -> None:
    app = _app()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#search_input", Input).has_focus
        hints = str(app.query_one("#status_bar", StatusBar).render())
        assert "esc blur" in hints
        assert "g/G" not in hints


@pytest.mark.asyncio
async def test_status_bar_switches_to_list_hints_after_search() -> None:
    app = _app()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "hint"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert (
            app.query_one("#results_table", SongTable).query_one(VimListView).has_focus
        )
        hints = str(app.query_one("#status_bar", StatusBar).render())
        assert "g/G" in hints
        assert "/ search" in hints

        await pilot.press("i")
        await pilot.pause()
        assert app.query_one("#search_input", Input).has_focus
        hints = str(app.query_one("#status_bar", StatusBar).render())
        assert "esc blur" in hints
        assert "g/G" not in hints
