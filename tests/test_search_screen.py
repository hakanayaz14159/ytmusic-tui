"""Textual pilot tests for SearchScreen."""

from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, ListView

from ytmusic_cli.music.types import Song
from ytmusic_cli.tui.search_screen import SearchScreen, SongListItem

SAMPLE_SONGS: list[Song] = [
    {
        "id": 1,
        "title": "Ambient Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 240,
        "url": "https://www.youtube.com/watch?v=synth101",
    },
    {
        "id": 2,
        "title": "Night Drive",
        "artist": "RetroWave",
        "album": "Neon Roads",
        "duration": 198,
        "url": "https://www.youtube.com/watch?v=night202",
    },
]


class SearchTestApp(App[None]):
    """Minimal app that pushes SearchScreen with injected mock services."""

    def __init__(
        self,
        search_service: MagicMock,
        playback_service: MagicMock,
    ) -> None:
        super().__init__()
        self.search_service = search_service
        self.playback_service = playback_service

    def compose(self) -> ComposeResult:
        yield Input(id="placeholder")

    def on_mount(self) -> None:
        self.push_screen(
            SearchScreen(
                search_service=self.search_service,
                playback_service=self.playback_service,
            )
        )


@pytest.fixture
def mock_search_service() -> MagicMock:
    service = MagicMock()
    service.search = MagicMock(return_value=SAMPLE_SONGS)
    return service


@pytest.fixture
def mock_playback_service() -> MagicMock:
    service = MagicMock()
    service.play_song = MagicMock()
    return service


@pytest.mark.asyncio
async def test_empty_search_query_triggers_warning_and_skips_search(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = SearchTestApp(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.screen.query_one("#search_input", Input)
        search_input.value = "   "
        await pilot.press("enter")
        await pilot.pause()

        # Assert
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
    # Arrange
    app = SearchTestApp(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.screen.query_one("#search_input", Input)
        search_input.value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # Assert
        mock_search_service.search.assert_called_once_with("ambient")
        results_list = app.screen.query_one("#results_list", ListView)
        assert len(results_list.children) == len(SAMPLE_SONGS)
        first_item = results_list.children[0]
        assert isinstance(first_item, SongListItem)
        assert first_item.song == SAMPLE_SONGS[0]
        assert results_list.has_focus is True


@pytest.mark.asyncio
async def test_selecting_result_triggers_play_song(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = SearchTestApp(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
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

        # Assert
        mock_playback_service.play_song.assert_called_once_with(SAMPLE_SONGS[0])
        notifications = list(app._notifications)
        assert any(
            n.severity == "information" and "Playing: Ambient Flow" in n.message
            for n in notifications
        )


@pytest.mark.asyncio
async def test_playback_failure_notifies_error_and_no_success_toast(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    mock_playback_service.play_song.side_effect = RuntimeError(
        "HTTP Error 403: Forbidden"
    )
    app = SearchTestApp(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
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

        # Assert
        notifications = list(app._notifications)
        assert any(
            n.severity == "error"
            and "Playback failed: HTTP Error 403: Forbidden" in n.message
            for n in notifications
        )
        assert not any(
            n.severity == "information" and "Playing: Ambient Flow" in n.message
            for n in notifications
        )


@pytest.mark.asyncio
async def test_missing_playback_service_notifies_error(
    mock_search_service: MagicMock,
) -> None:
    # Arrange
    app = SearchTestApp(mock_search_service, None)  # type: ignore[arg-type]

    # Act
    async with app.run_test() as pilot:
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

        # Assert
        notifications = list(app._notifications)
        assert any(
            n.severity == "error" and "Playback service is not available" in n.message
            for n in notifications
        )


@pytest.mark.asyncio
async def test_escape_key_dismisses_search_screen(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = SearchTestApp(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, SearchScreen)
        await pilot.press("escape")
        await pilot.pause()

        # Assert
        assert not isinstance(app.screen, SearchScreen)
