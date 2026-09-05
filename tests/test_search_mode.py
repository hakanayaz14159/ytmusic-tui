"""Textual pilot tests for Search mode."""

import threading
from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, Label

from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.types import Song
from ytmusic_cli.tui.format import format_song_line
from ytmusic_cli.tui.widgets.song_table import SongRow, SongTable

SAMPLE_SONGS: list[Song] = [
    {
        "video_id": "synth101",
        "title": "Ambient Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 240,
    },
    {
        "video_id": "night202",
        "title": "Night Drive",
        "artist": "RetroWave",
        "album": "Neon Roads",
        "duration": 198,
    },
]


@pytest.fixture
def mock_search_service() -> MagicMock:
    service = MagicMock()
    service.search = MagicMock(return_value=SAMPLE_SONGS)
    return service


@pytest.fixture
def mock_playback_service() -> MagicMock:
    service = MagicMock()
    service.sync_playback = MagicMock()
    return service


def _make_app(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> YTMusicApp:
    return YTMusicApp(
        search_service=mock_search_service,
        playback_service=mock_playback_service,
    )


@pytest.mark.asyncio
async def test_empty_search_query_triggers_warning_and_skips_search(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        search_input.value = "   "
        await pilot.press("enter")
        await pilot.pause()

        notifications = list(app._notifications)
        assert any(
            n.severity == "warning" and "search query" in n.message.lower()
            for n in notifications
        )
        mock_search_service.search.assert_not_called()


@pytest.mark.asyncio
async def test_submitting_query_calls_search_and_populates_results(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        search_input.value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_search_service.search.assert_called_once()
        assert mock_search_service.search.call_args.args[0] == "ambient"
        table = app.query_one("#results_table", SongTable)
        assert len(table._songs) == len(SAMPLE_SONGS)
        first = table.get_selected_song()
        assert first == SAMPLE_SONGS[0]


@pytest.mark.asyncio
async def test_selecting_result_delegates_play_song_to_app(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    app.play_song = MagicMock()

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        search_input.value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        table = app.query_one("#results_table", SongTable)
        table.query_one("ListView").index = 0
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        app.play_song.assert_called_once_with(SAMPLE_SONGS[0])


@pytest.mark.asyncio
async def test_search_results_show_duration(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        table = app.query_one("#results_table", SongTable)
        row = table.query_one(SongRow)
        assert "04:00" in format_song_line(SAMPLE_SONGS[0])
        assert "04:00" in str(row.query_one(Label).content)


def test_format_song_line_uses_unknown_uploader_fallback() -> None:
    song: Song = {
        "video_id": "missing01",
        "title": "Untitled",
        "artist": None,
        "album": None,
        "duration": 12,
    }

    line = format_song_line(song)

    assert "Unknown Uploader" in line
    assert "Unknown Artist" not in line


@pytest.mark.asyncio
async def test_song_table_header_labels_uploader_not_artist(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#results_table", SongTable)
        header = str(table.query_one("#song_table_header", Label).content)

        assert "Uploader" in header
        assert "Artist" not in header


@pytest.mark.asyncio
async def test_search_status_shows_searching_then_count_and_hides_stale_table(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def _blocked_search(query: str, max_results: int = 10) -> list[Song]:
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("search was not released")
        return SAMPLE_SONGS

    mock_search_service.search.side_effect = _blocked_search
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        status = app.query_one("#search_status", Label)
        table = app.query_one("#results_table", SongTable)
        assert "Type a query and press Enter." in str(status.content)
        idle_visible = table.display
        assert idle_visible is False

        app.query_one("#search_input", Input).value = "ambient"
        await pilot.press("enter")
        for _ in range(20):
            if started.is_set():
                break
            await pilot.pause()

        assert started.is_set()
        assert "Searching “ambient”" in str(status.content)
        searching_visible = table.display
        assert searching_visible is False

        release.set()
        visible = False
        for _ in range(20):
            visible = table.display
            if visible:
                break
            await pilot.pause()

        assert visible is True
        assert "2 results for “ambient”" in str(status.content)
        assert len(table._songs) == len(SAMPLE_SONGS)


@pytest.mark.asyncio
async def test_search_status_reports_no_results_for_query(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    mock_search_service.search.return_value = []
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "xyz"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        status = app.query_one("#search_status", Label)
        table = app.query_one("#results_table", SongTable)
        assert "No results for “xyz”." in str(status.content)
        no_results_visible = table.display
        assert no_results_visible is False
