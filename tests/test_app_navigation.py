"""Textual pilot tests for YTMusicApp keybindings and shell wiring."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from textual.widgets import Input

from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.tui.modals.help import HelpModal
from ytmusic_cli.tui.modes.search import SearchMode
from ytmusic_cli.tui.shell import AppShell
from ytmusic_cli.tui.widgets.now_playing import NowPlaying


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
    service.play_next = MagicMock()
    service.play_previous = MagicMock()
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
async def test_app_lands_on_search_with_query_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        shell = app.query_one(AppShell)
        assert shell.current_mode == "search"
        assert app.query_one("#search", SearchMode).display is True
        assert app.query_one("#search_input", Input).has_focus is True


@pytest.mark.asyncio
async def test_slash_focuses_search_input(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "search"
        assert app.query_one("#search_input", Input).has_focus is True


@pytest.mark.asyncio
async def test_now_playing_stays_mounted_after_search_focus(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        bar = app.query_one("#now_playing", NowPlaying)
        assert bar.is_mounted


@pytest.mark.asyncio
async def test_pressing_space_calls_playback_toggle_when_list_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        mock_playback_service.toggle.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_plus_calls_volume_up(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("+")
        await pilot.pause()
        mock_playback_service.volume_up.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_equals_calls_volume_up(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("equals_sign")
        await pilot.pause()
        mock_playback_service.volume_up.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_minus_calls_volume_down(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("-")
        await pilot.pause()
        mock_playback_service.volume_down.assert_called_once()


@pytest.mark.asyncio
async def test_digit_two_switches_to_queue_mode(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "queue"


@pytest.mark.asyncio
async def test_question_mark_opens_help_modal(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpModal)


@pytest.mark.asyncio
async def test_q_does_not_quit_while_search_input_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert app.is_running
        search_input = app.query_one("#search_input", Input)
        assert "q" in search_input.value


@pytest.mark.asyncio
async def test_escape_then_q_quits(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    assert not app.is_running


def test_on_mount_schedules_playback_sync_interval(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    set_interval = mocker.patch.object(app, "set_interval")

    app.on_mount()

    set_interval.assert_called_once_with(1.0, app.playback_service.sync_playback)
