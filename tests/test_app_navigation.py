"""Textual pilot tests for YTMusicApp keybindings and composition wiring."""

from unittest.mock import MagicMock

import pytest

from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.tui.player_bar import PlayerBar
from ytmusic_cli.tui.search_screen import SearchScreen


@pytest.fixture
def mock_search_service() -> MagicMock:
    service = MagicMock()
    service.search = MagicMock(return_value=[])
    return service


@pytest.fixture
def mock_playback_service() -> MagicMock:
    service = MagicMock()
    service.toggle = MagicMock()
    service.volume_up = MagicMock()
    service.volume_down = MagicMock()
    service.play_song = MagicMock()
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
async def test_pressing_s_pushes_search_screen(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = _make_app(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()

        # Assert
        assert isinstance(app.screen, SearchScreen)


@pytest.mark.asyncio
async def test_pressing_slash_pushes_search_screen(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = _make_app(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()

        # Assert
        assert isinstance(app.screen, SearchScreen)


@pytest.mark.asyncio
async def test_pressing_space_calls_playback_toggle(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = _make_app(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        # Assert
        mock_playback_service.toggle.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_plus_calls_volume_up(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = _make_app(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("+")
        await pilot.pause()

        # Assert
        mock_playback_service.volume_up.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_equals_calls_volume_up(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = _make_app(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("=")
        await pilot.pause()

        # Assert
        mock_playback_service.volume_up.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_minus_calls_volume_down(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = _make_app(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("-")
        await pilot.pause()

        # Assert
        mock_playback_service.volume_down.assert_called_once()


@pytest.mark.asyncio
async def test_player_bar_is_present_in_dom(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    # Arrange
    app = _make_app(mock_search_service, mock_playback_service)

    # Act
    async with app.run_test() as pilot:
        await pilot.pause()

        # Assert
        bar = app.query_one("#player_bar", PlayerBar)
        assert bar is not None
