"""End-to-end integration tests for search-to-playback flow across layers."""

from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, Static

from tests.conftest import make_test_app
from ytmusic_cli.exceptions import StreamExtractionError
from ytmusic_cli.music.services import PlaybackService, SearchService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import AudioStream, PlaybackStatus
from ytmusic_cli.tui.widgets.now_playing import NowPlaying
from ytmusic_cli.tui.widgets.song_table import SongTable, VimListView


@pytest.mark.asyncio
async def test_search_and_play_flow_updates_player_and_bar(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    expected_stream: AudioStream = {
        "url": "https://stream.example.com/audio.m4a",
        "http_headers": {
            "User-Agent": "test-agent",
            "Referer": "https://www.youtube.com/",
        },
    }
    mock_youtube.get_stream.return_value = expected_stream

    state = AppState()
    search_service = SearchService(source=mock_youtube)
    playback_service = PlaybackService(
        player=mock_player,
        source=mock_youtube,
        state=state,
    )
    app = make_test_app(
        search_service=search_service,
        playback_service=playback_service,
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        player_bar = app.query_one("#now_playing", NowPlaying)
        assert player_bar.is_mounted

        search_input = app.query_one("#search_input", Input)
        search_input.value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        results_table = app.query_one("#results_table", SongTable)
        assert len(results_table._songs) > 0

        results_table.query_one(VimListView).index = 0
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_youtube.get_stream.assert_called_once_with("sample1")
        mock_player.play.assert_called_once_with(expected_stream)
        mock_player.set_volume.assert_called_with(80)

        assert state.playback_state.get()["status"] == PlaybackStatus.PLAYING
        current = state.current_song.get()
        assert current is not None
        assert current["title"] == "Sample Song 1"

        assert app.query_one("#now_playing", NowPlaying).is_mounted
        title_text = str(player_bar.query_one("#np_title", Static).content)
        assert "▶" in title_text
        assert "Sample Song 1" in title_text


@pytest.mark.asyncio
async def test_search_and_play_403_error_leaves_state_stopped_and_notifies_user(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    mock_youtube.get_stream.side_effect = StreamExtractionError(
        "HTTP Error 403: Forbidden"
    )

    state = AppState()
    search_service = SearchService(source=mock_youtube)
    playback_service = PlaybackService(
        player=mock_player,
        source=mock_youtube,
        state=state,
    )
    app = make_test_app(
        search_service=search_service,
        playback_service=playback_service,
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        search_input = app.query_one("#search_input", Input)
        search_input.value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        results_table = app.query_one("#results_table", SongTable)
        results_table.query_one(VimListView).index = 0
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_player.play.assert_not_called()

        assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
        assert state.current_song.get() is None

        player_bar = app.query_one("#now_playing", NowPlaying)
        title_text = str(player_bar.query_one("#np_title", Static).content)
        assert "■" in title_text
        assert "[No track playing]" in title_text

        notifications = list(app._notifications)
        assert any(
            n.severity == "error" and "HTTP Error 403: Forbidden" in n.message
            for n in notifications
        )
        assert not any(
            n.severity == "information" and "Playing:" in n.message
            for n in notifications
        )
