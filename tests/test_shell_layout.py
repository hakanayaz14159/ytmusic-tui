"""Layout tests: now-playing chrome must not sit under the status bar."""

from unittest.mock import MagicMock

import pytest
from textual.widgets import Static

from tests.conftest import make_test_app
from ytmusic_tui.music.services import PlaybackService, SearchService
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import PlaybackStatus, Song
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.tui.widgets.now_playing import NowPlaying
from ytmusic_tui.tui.widgets.status_bar import StatusBar


def _make_app(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> YTMusicApp:
    state = AppState()
    return make_test_app(
        search_service=SearchService(source=mock_youtube),
        playback_service=PlaybackService(
            player=mock_player,
            source=mock_youtube,
            state=state,
        ),
    )


def _assert_no_overlap(now_playing: NowPlaying, status: StatusBar) -> None:
    overlap = now_playing.region.intersection(status.region)
    assert overlap.area == 0
    assert now_playing.region.bottom <= status.region.y


@pytest.mark.asyncio
async def test_now_playing_and_status_do_not_overlap_at_full_height(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app = _make_app(mock_youtube, mock_player)
    song: Song = {
        "video_id": "layout1",
        "title": "Layout Track",
        "artist": "Layout Artist",
        "album": None,
        "duration": 180,
    }

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        now_playing = app.query_one("#now_playing", NowPlaying)
        status = app.query_one("#status_bar", StatusBar)
        _assert_no_overlap(now_playing, status)

        title = now_playing.query_one("#np_title", Static)
        detail = now_playing.query_one("#np_detail", Static)
        assert title.display is True
        assert detail.display is True

        state = AppState()
        state.current_song.set(song)
        state.playback_state.set(
            {
                "status": PlaybackStatus.PLAYING,
                "volume": 80,
                "position": 0.0,
                "duration": 180,
            }
        )
        await pilot.pause()

        assert "▶" in str(title.content)
        assert "Layout Track" in str(title.content)
        _assert_no_overlap(now_playing, status)


@pytest.mark.asyncio
async def test_compact_now_playing_stays_above_status_bar(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app = _make_app(mock_youtube, mock_player)

    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        now_playing = app.query_one("#now_playing", NowPlaying)
        status = app.query_one("#status_bar", StatusBar)
        title = now_playing.query_one("#np_title", Static)
        detail = now_playing.query_one("#np_detail", Static)

        assert now_playing.has_class("-compact")
        assert detail.display is False
        assert title.display is True
        _assert_no_overlap(now_playing, status)
        assert "■" in str(title.content)
