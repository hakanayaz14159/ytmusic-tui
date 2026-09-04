"""End-to-end integration tests for search-to-playback flow across layers."""

from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, ListView, Static

from ytmusic_cli.exceptions import StreamExtractionError
from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.services import PlaybackService, SearchService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import AudioStream, PlaybackStatus
from ytmusic_cli.tui.player_bar import PlayerBar
from ytmusic_cli.tui.search_screen import SearchScreen


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
    app = YTMusicApp(
        search_service=search_service,
        playback_service=playback_service,
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        # Open search via shortcut
        await pilot.press("/")
        await pilot.pause()
        assert isinstance(app.screen, SearchScreen)

        # Submit search query
        search_input = app.screen.query_one("#search_input", Input)
        search_input.value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # Results should be populated and list focused
        results_list = app.screen.query_one("#results_list", ListView)
        assert len(results_list.children) > 0
        assert results_list.has_focus is True

        # Select first result and press enter to play
        results_list.index = 0
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # Verify YouTube get_stream and Player play were called with full stream info
        mock_youtube.get_stream.assert_called_once_with(
            "https://www.youtube.com/watch?v=sample1"
        )
        mock_player.play.assert_called_once_with(expected_stream)
        mock_player.set_volume.assert_called_with(80)

        # Verify AppState reflects playback
        assert state.playback_state.get()["status"] == PlaybackStatus.PLAYING
        assert state.current_song.get() is not None
        assert state.current_song.get()["title"] == "Sample Song 1"  # type: ignore[index]

        # Verify PlayerBar reflects playing state
        player_bar = app.query_one(PlayerBar)
        status_text = str(player_bar.query_one("#player_status", Static).content)
        track_text = str(player_bar.query_one("#player_track", Static).content)
        assert "▶" in status_text
        assert "Sample Song 1" in track_text


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
    app = YTMusicApp(
        search_service=search_service,
        playback_service=playback_service,
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()

        search_input = app.screen.query_one("#search_input", Input)
        search_input.value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        results_list = app.screen.query_one("#results_list", ListView)
        results_list.index = 0
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # Player must NOT have been called
        mock_player.play.assert_not_called()

        # State must remain stopped and no current song
        assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
        assert state.current_song.get() is None

        # PlayerBar must remain stopped
        player_bar = app.query_one(PlayerBar)
        status_text = str(player_bar.query_one("#player_status", Static).content)
        track_text = str(player_bar.query_one("#player_track", Static).content)
        assert "■" in status_text
        assert "[No track playing]" in track_text

        # User must see error notification with 403
        notifications = list(app._notifications)
        assert any(
            n.severity == "error" and "HTTP Error 403: Forbidden" in n.message
            for n in notifications
        )
        assert not any(
            n.severity == "information" and "Playing:" in n.message
            for n in notifications
        )
