"""Textual pilot tests for Search mode."""

import threading
from unittest.mock import MagicMock

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Label

from ytmusic_cli.consts import DEFAULT_SUGGEST_LIMIT
from ytmusic_cli.exceptions import SuggestionError
from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.types import Song
from ytmusic_cli.tui.format import format_song_line
from ytmusic_cli.tui.modes.search import SearchMode
from ytmusic_cli.tui.widgets.song_table import SongRow, SongTable
from ytmusic_cli.tui.widgets.suggestion_list import SuggestionList

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


SAMPLE_SUGGESTIONS = ["beatles", "beatles yesterday"]


@pytest.fixture
def mock_search_service() -> MagicMock:
    service = MagicMock()
    service.search = MagicMock(return_value=SAMPLE_SONGS)
    service.suggest = MagicMock(return_value=[])
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


async def _await_suggestions(pilot: Pilot[None], app: YTMusicApp) -> None:
    suggestions = app.query_one("#suggestion_list", SuggestionList)
    for _ in range(20):
        if suggestions.display and suggestions.option_count > 0:
            return
        await pilot.pause()
    raise AssertionError("suggestions did not appear")


async def _load_suggestions(
    pilot: Pilot[None],
    app: YTMusicApp,
    query: str = "beat",
) -> None:
    app.query_one("#search_input", Input).value = query
    app.query_one(SearchMode)._request_suggestions()
    await _await_suggestions(pilot, app)


@pytest.mark.asyncio
async def test_short_query_does_not_show_suggestions(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "a"
        await pilot.pause()

        suggestions = app.query_one("#suggestion_list", SuggestionList)
        assert suggestions.display is False
        mock_search_service.suggest.assert_not_called()


@pytest.mark.asyncio
async def test_typing_query_populates_suggestion_list(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    started = threading.Event()

    def _suggest(query: str, max_results: int = DEFAULT_SUGGEST_LIMIT) -> list[str]:
        started.set()
        return SAMPLE_SUGGESTIONS

    mock_search_service.suggest.side_effect = _suggest
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _load_suggestions(pilot, app)

        assert started.is_set()
        mock_search_service.suggest.assert_called()
        assert mock_search_service.suggest.call_args.args[0] == "beat"
        suggestions = app.query_one("#suggestion_list", SuggestionList)
        assert suggestions.display is True
        assert suggestions.option_count == 2


@pytest.mark.asyncio
async def test_down_fills_input_from_highlighted_suggestion(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    mock_search_service.suggest.return_value = SAMPLE_SUGGESTIONS
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _load_suggestions(pilot, app)
        await pilot.press("down")
        await pilot.pause()

        assert app.query_one("#search_input", Input).value == "beatles"
        assert app.query_one("#suggestion_list", SuggestionList).selected_query() == (
            "beatles"
        )


@pytest.mark.asyncio
async def test_up_from_first_suggestion_restores_typed_query(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    mock_search_service.suggest.return_value = SAMPLE_SUGGESTIONS
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _load_suggestions(pilot, app)
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()

        assert app.query_one("#search_input", Input).value == "beat"
        assert (
            app.query_one("#suggestion_list", SuggestionList).selected_query() is None
        )


@pytest.mark.asyncio
async def test_enter_searches_completed_query_and_hides_suggestions(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    mock_search_service.suggest.return_value = SAMPLE_SUGGESTIONS
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _load_suggestions(pilot, app)
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_search_service.search.assert_called_once()
        assert mock_search_service.search.call_args.args[0] == "beatles"
        assert app.query_one("#suggestion_list", SuggestionList).display is False


@pytest.mark.asyncio
async def test_escape_hides_suggestions_and_keeps_input_focus(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    mock_search_service.suggest.return_value = SAMPLE_SUGGESTIONS
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _load_suggestions(pilot, app)
        await pilot.press("escape")
        await pilot.pause()

        suggestions = app.query_one("#suggestion_list", SuggestionList)
        assert suggestions.display is False
        focused = app.focused
        assert focused is not None
        assert focused.id == "search_input"


@pytest.mark.asyncio
async def test_suggest_failure_hides_list_without_notify(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    mock_search_service.suggest.side_effect = SuggestionError("suggest down")
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "beat"
        app.query_one(SearchMode)._request_suggestions()
        for _ in range(20):
            if mock_search_service.suggest.called:
                break
            await pilot.pause()
        await pilot.pause()

        assert app.query_one("#suggestion_list", SuggestionList).display is False
        notifications = list(app._notifications)
        assert not any("suggest down" in n.message.lower() for n in notifications)
