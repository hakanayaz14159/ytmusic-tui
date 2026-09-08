"""Textual pilot tests for YTMusicApp keybindings and shell wiring."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from textual.widgets import Input

from tests.conftest import make_test_app
from ytmusic_tui.music.types import PlaybackTick, PlaybackTickAction, SkipKeymap
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.tui.modals.help import HelpModal
from ytmusic_tui.tui.modes.search import SearchMode
from ytmusic_tui.tui.shell import AppShell
from ytmusic_tui.tui.widgets.now_playing import NowPlaying


@pytest.fixture
def mock_search_service() -> MagicMock:
    service = MagicMock()
    service.search = MagicMock(return_value=[])
    service.suggest = MagicMock(return_value=[])
    return service


@pytest.fixture
def mock_playback_service() -> MagicMock:
    service = MagicMock()
    service.toggle = MagicMock()
    service.volume_up = MagicMock()
    service.volume_down = MagicMock()
    service.seek_forward = MagicMock()
    service.seek_backward = MagicMock()
    service.play_song = MagicMock()
    service.play_next = MagicMock()
    service.play_previous = MagicMock()
    service.sync_playback = MagicMock()
    return service


def _make_app(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> YTMusicApp:
    return make_test_app(
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
        await pilot.press("escape")
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
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("-")
        await pilot.pause()
        mock_playback_service.volume_down.assert_called_once()


@pytest.mark.asyncio
async def test_volume_keys_insert_when_search_input_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        assert search_input.has_focus is True
        await pilot.press("+")
        await pilot.press("equals_sign")
        await pilot.press("-")
        await pilot.pause()

        assert "+" in search_input.value
        assert "=" in search_input.value
        assert "-" in search_input.value
        mock_playback_service.volume_up.assert_not_called()
        mock_playback_service.volume_down.assert_not_called()


@pytest.mark.asyncio
async def test_pressing_e_calls_seek_backward(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        mock_playback_service.seek_backward.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_r_calls_seek_forward(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        mock_playback_service.seek_forward.assert_called_once()


@pytest.mark.asyncio
async def test_seek_keys_insert_when_search_input_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        assert search_input.has_focus is True
        await pilot.press("e")
        await pilot.press("r")
        await pilot.pause()

        assert "e" in search_input.value
        assert "r" in search_input.value
        mock_playback_service.seek_backward.assert_not_called()
        mock_playback_service.seek_forward.assert_not_called()


@pytest.mark.asyncio
async def test_pressing_z_calls_play_next(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_next = mocker.patch.object(app, "_play_next")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.focused, Input)
        await pilot.press("z")
        await pilot.pause()
        play_next.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_less_than_sign_calls_play_previous(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_previous = mocker.patch.object(app, "_play_previous")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.focused, Input)
        await pilot.press("<")
        await pilot.pause()
        play_previous.assert_called_once()


@pytest.mark.asyncio
async def test_pressing_less_than_alias_does_not_skip_previous(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_previous = mocker.patch.object(app, "_play_previous")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("less_than")
        await pilot.pause()
        play_previous.assert_not_called()


@pytest.mark.asyncio
async def test_queue_skip_keys_insert_when_search_input_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_next = mocker.patch.object(app, "_play_next")
    play_previous = mocker.patch.object(app, "_play_previous")

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        assert search_input.has_focus is True
        await pilot.press("z")
        await pilot.press("<")
        await pilot.pause()

        assert "z" in search_input.value
        assert "<" in search_input.value
        play_next.assert_not_called()
        play_previous.assert_not_called()


@pytest.mark.asyncio
async def test_pressing_x_does_not_skip_on_iso(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_next = mocker.patch.object(app, "_play_next")
    play_previous = mocker.patch.object(app, "_play_previous")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app._skip_keymap is SkipKeymap.ISO
        assert not isinstance(app.focused, Input)
        await pilot.press("x")
        await pilot.pause()
        play_next.assert_not_called()
        play_previous.assert_not_called()


@pytest.mark.asyncio
async def test_ansi_z_calls_play_previous(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_next = mocker.patch.object(app, "_play_next")
    play_previous = mocker.patch.object(app, "_play_previous")

    async with app.run_test() as pilot:
        await pilot.pause()
        app._skip_keymap = SkipKeymap.ANSI
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.focused, Input)
        await pilot.press("z")
        await pilot.pause()
        play_previous.assert_called_once()
        play_next.assert_not_called()


@pytest.mark.asyncio
async def test_ansi_x_calls_play_next(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_next = mocker.patch.object(app, "_play_next")
    play_previous = mocker.patch.object(app, "_play_previous")

    async with app.run_test() as pilot:
        await pilot.pause()
        app._skip_keymap = SkipKeymap.ANSI
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        play_next.assert_called_once()
        play_previous.assert_not_called()


@pytest.mark.asyncio
async def test_ansi_less_than_does_not_skip(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_previous = mocker.patch.object(app, "_play_previous")

    async with app.run_test() as pilot:
        await pilot.pause()
        app._skip_keymap = SkipKeymap.ANSI
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("<")
        await pilot.pause()
        play_previous.assert_not_called()


@pytest.mark.asyncio
async def test_x_inserts_when_search_input_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)
    play_next = mocker.patch.object(app, "_play_next")

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        assert search_input.has_focus is True
        await pilot.press("x")
        await pilot.pause()
        assert "x" in search_input.value
        play_next.assert_not_called()


@pytest.mark.asyncio
async def test_shift_a_inserts_when_search_input_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        await pilot.press("A")
        await pilot.pause()

        assert "A" in search_input.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("digit", "mode"),
    [
        ("1", "search"),
        ("2", "queue"),
        ("3", "playlists"),
        ("4", "profiles"),
        ("5", "settings"),
    ],
)
async def test_digit_switches_mode_when_search_input_not_focused(
    digit: str,
    mode: str,
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press(digit)
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == mode


@pytest.mark.asyncio
@pytest.mark.parametrize("digit", ["1", "2", "3", "4", "5"])
async def test_digit_inserts_when_search_input_focused(
    digit: str,
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        assert search_input.has_focus is True
        await pilot.press(digit)
        await pilot.pause()
        assert digit in search_input.value
        assert app.query_one(AppShell).current_mode == "search"


@pytest.mark.asyncio
async def test_shift_l_cycles_to_next_mode_when_not_in_input(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("L")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "queue"


@pytest.mark.asyncio
async def test_shift_h_cycles_to_previous_mode_when_not_in_input(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("H")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "settings"


@pytest.mark.asyncio
async def test_shift_h_and_l_insert_when_search_input_focused(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
) -> None:
    app = _make_app(mock_search_service, mock_playback_service)

    async with app.run_test() as pilot:
        await pilot.pause()
        search_input = app.query_one("#search_input", Input)
        assert search_input.has_focus is True
        await pilot.press("H")
        await pilot.press("L")
        await pilot.pause()
        assert "H" in search_input.value
        assert "L" in search_input.value
        assert app.query_one(AppShell).current_mode == "search"


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

    set_interval.assert_called_once_with(1.0, app._on_playback_tick)


def test_playback_tick_notifies_on_engine_failure(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_playback_service.sync_playback.return_value = PlaybackTick(
        PlaybackTickAction.FAILED,
        "Playback failed to start",
    )
    app = _make_app(mock_search_service, mock_playback_service)
    notify = mocker.patch.object(app, "notify")

    app._on_playback_tick()

    notify.assert_called_once()
    assert notify.call_args[0][0] == "Playback failed to start"
    assert notify.call_args[1]["severity"] == "error"
    mock_playback_service.advance_to_next.assert_not_called()


def test_playback_tick_dispatches_play_next_on_ended(
    mock_search_service: MagicMock,
    mock_playback_service: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_playback_service.sync_playback.return_value = PlaybackTick(
        PlaybackTickAction.ENDED
    )
    app = _make_app(mock_search_service, mock_playback_service)
    play_next = mocker.patch.object(app, "_play_next")

    app._on_playback_tick()

    play_next.assert_called_once()
