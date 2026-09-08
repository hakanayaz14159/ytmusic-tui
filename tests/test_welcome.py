"""Welcome session gate: wordmark, profile pick, and startup skip."""

from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from textual.widgets import Input, Static

from tests.conftest import make_test_app
from ytmusic_tui.db.repositories import AppConfigRepository, UserRepository
from ytmusic_tui.main import YTMusicApp
from ytmusic_tui.music.services import AccountService
from ytmusic_tui.music.state import AppState
from ytmusic_tui.tui.modes.search import SearchMode
from ytmusic_tui.tui.shell import AppShell
from ytmusic_tui.tui.welcome import WORDMARK_COMPACT, WORDMARK_FULL, WelcomeScreen
from ytmusic_tui.tui.widgets.select_list import SelectList


def _accounts() -> AccountService:
    return AccountService(UserRepository(), AppState(), AppConfigRepository())


def _welcome_app(
    service: AccountService,
    *,
    show_welcome: bool | None,
    playback: MagicMock | None = None,
) -> YTMusicApp:
    if playback is None:
        playback = MagicMock()
        playback.sync_playback = MagicMock()
        playback.toggle = MagicMock()
    return make_test_app(
        search_service=MagicMock(),
        playback_service=playback,
        account_service=service,
        show_welcome=show_welcome,
    )


@pytest.mark.asyncio
async def test_welcome_enter_selects_profile_and_lands_on_search(
    test_db: SqliteDatabase,
) -> None:
    state = AppState()
    service = _accounts()
    first = service.create_user("alpha")
    service.create_user("beta")
    app = _welcome_app(service, show_welcome=True)

    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        welcome = app.screen
        assert isinstance(welcome, WelcomeScreen)
        names = [
            option.prompt
            for option in welcome.query_one("#welcome_profiles", SelectList).options
        ]
        assert names == ["alpha", "beta"]
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.screen is not welcome
        assert app.query_one(AppShell).current_mode == "search"
        assert app.query_one("#search", SearchMode).display is True
        assert app.query_one("#search_input", Input).has_focus is True
        current = state.current_user.get()
        assert current is not None
        assert current["id"] == first["id"]


@pytest.mark.asyncio
async def test_welcome_n_creates_selects_and_enters_player(
    test_db: SqliteDatabase,
) -> None:
    state = AppState()
    service = _accounts()
    service.create_user("keep")
    app = _welcome_app(service, show_welcome=True)

    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#prompt_input", Input).value = "newone"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        current = state.current_user.get()
        assert current is not None
        assert current["username"] == "newone"
        assert not isinstance(app.screen, WelcomeScreen)
        assert app.query_one("#search_input", Input).has_focus is True


@pytest.mark.asyncio
async def test_welcome_q_exits(test_db: SqliteDatabase) -> None:
    service = _accounts()
    service.create_user("keep")
    app = _welcome_app(service, show_welcome=True)

    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    assert not app.is_running


@pytest.mark.asyncio
async def test_welcome_blocks_player_keys(test_db: SqliteDatabase) -> None:
    service = _accounts()
    service.create_user("keep")
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    playback.toggle = MagicMock()
    app = _welcome_app(service, show_welcome=True, playback=playback)

    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("1")
        await pilot.press("space")
        await pilot.press("/")
        await pilot.pause()
        assert isinstance(app.screen, WelcomeScreen)
        playback.toggle.assert_not_called()
        assert app.screen.query_one("#welcome_profiles", SelectList).has_focus is True


@pytest.mark.asyncio
async def test_skip_welcome_selects_default_profile(
    test_db: SqliteDatabase,
) -> None:
    state = AppState()
    service = _accounts()
    service.create_user("alpha")
    beta = service.create_user("beta")
    service.save_startup({"skip_welcome": True, "default_user_id": beta["id"]})
    app = _welcome_app(service, show_welcome=None)

    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert not isinstance(app.screen, WelcomeScreen)
        current = state.current_user.get()
        assert current is not None
        assert current["id"] == beta["id"]
        assert app.query_one(AppShell).current_mode == "search"
        assert app.query_one("#search_input", Input).has_focus is True


@pytest.mark.asyncio
async def test_skip_welcome_without_default_shows_gate(
    test_db: SqliteDatabase,
) -> None:
    service = _accounts()
    service.create_user("alpha")
    service.save_startup({"skip_welcome": True, "default_user_id": None})
    app = _welcome_app(service, show_welcome=None)

    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, WelcomeScreen)


@pytest.mark.asyncio
async def test_welcome_wordmark_uses_ascii_art(
    test_db: SqliteDatabase,
) -> None:
    service = _accounts()
    service.create_user("keep")
    app = _welcome_app(service, show_welcome=True)

    async with app.run_test(size=(80, 24)) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        welcome = app.screen
        assert isinstance(welcome, WelcomeScreen)
        assert str(welcome.query_one("#welcome_mark", Static).content) == WORDMARK_FULL
        assert str(welcome.query_one("#welcome_tui", Static).content) == "T U I"
        assert "YTMUSIC" not in WORDMARK_FULL
        assert "╔═╗" in WORDMARK_FULL
        assert not set(WORDMARK_FULL) & set("┬┌└┘│┴")


@pytest.mark.asyncio
async def test_welcome_compact_height_hides_tagline(
    test_db: SqliteDatabase,
) -> None:
    service = _accounts()
    service.create_user("keep")
    app = _welcome_app(service, show_welcome=True)

    async with app.run_test(size=(80, 20)) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        tag = app.screen.query_one("#welcome_tag", Static)
        assert tag.display is False
        assert (
            str(app.screen.query_one("#welcome_mark", Static).content)
            == WORDMARK_COMPACT
        )
