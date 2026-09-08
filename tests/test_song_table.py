"""Pilot tests for VimListView motion and SongTable search re-entry."""

from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import Input, Label, ListItem

from tests.conftest import make_test_app
from ytmusic_tui.music.types import Song
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.tui.widgets.list_motion import motion_step
from ytmusic_tui.tui.widgets.song_table import SongTable, VimListView

_ITEM_COUNT = 40

SAMPLE_SONGS: list[Song] = [
    {
        "video_id": "motion1",
        "title": "First Track",
        "artist": "Artist",
        "album": None,
        "duration": 120,
    },
    {
        "video_id": "motion2",
        "title": "Second Track",
        "artist": "Artist",
        "album": None,
        "duration": 130,
    },
]


class VimListHarness(App[None]):
    def __init__(self, count: int = _ITEM_COUNT) -> None:
        super().__init__()
        self._count = count

    def compose(self) -> ComposeResult:
        yield VimListView(
            *[ListItem(Label(f"item-{index}")) for index in range(self._count)],
            id="vim_list",
        )


def _listing(app: App[None]) -> VimListView:
    return app.query_one("#vim_list", VimListView)


@pytest.mark.parametrize(
    ("height", "half", "expected"),
    [
        (0, False, 1),
        (0, True, 1),
        (-3, False, 1),
        (10, False, 10),
        (10, True, 5),
        (1, True, 1),
        (3, True, 1),
    ],
)
def test_motion_step_clamps_to_at_least_one(
    height: int, half: bool, expected: int
) -> None:
    assert motion_step(height, half=half) == expected


@pytest.mark.asyncio
async def test_vim_list_view_g_and_G_jump_to_ends() -> None:
    app = VimListHarness()
    async with app.run_test(size=(80, 12)) as pilot:
        listing = _listing(app)
        listing.focus()
        listing.index = 12
        await pilot.press("g")
        await pilot.pause()
        assert listing.index == 0

        await pilot.press("G")
        await pilot.pause()
        assert listing.index == _ITEM_COUNT - 1


@pytest.mark.asyncio
async def test_vim_list_view_page_keys_move_and_clamp_highlight() -> None:
    app = VimListHarness()
    async with app.run_test(size=(80, 12)) as pilot:
        listing = _listing(app)
        listing.focus()
        listing.index = 0
        await pilot.press("ctrl+d")
        await pilot.pause()
        half_down = listing.index
        assert half_down is not None and half_down > 0

        listing.index = 0
        await pilot.press("ctrl+f")
        await pilot.pause()
        page_down = listing.index
        assert page_down is not None and page_down >= half_down

        listing.index = 0
        await pilot.press("pagedown")
        await pilot.pause()
        assert listing.index == page_down

        listing.index = _ITEM_COUNT - 1
        await pilot.press("ctrl+u")
        await pilot.pause()
        half_up = listing.index
        assert half_up is not None and half_up < _ITEM_COUNT - 1

        listing.index = _ITEM_COUNT - 1
        await pilot.press("ctrl+b")
        await pilot.pause()
        page_up = listing.index
        assert page_up is not None and page_up <= half_up

        listing.index = _ITEM_COUNT - 1
        await pilot.press("pageup")
        await pilot.pause()
        assert listing.index == page_up

        listing.index = 0
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert listing.index == 0

        listing.index = _ITEM_COUNT - 1
        await pilot.press("ctrl+f")
        await pilot.pause()
        assert listing.index == _ITEM_COUNT - 1


@pytest.mark.asyncio
async def test_vim_list_view_j_k_still_move_one_row() -> None:
    app = VimListHarness()
    async with app.run_test(size=(80, 12)) as pilot:
        listing = _listing(app)
        listing.focus()
        listing.index = 2
        await pilot.press("j")
        await pilot.pause()
        assert listing.index == 3
        await pilot.press("k")
        await pilot.pause()
        assert listing.index == 2


@pytest.mark.asyncio
async def test_vim_list_view_empty_and_single_item_do_not_crash() -> None:
    empty = VimListHarness(0)
    async with empty.run_test(size=(80, 12)) as pilot:
        listing = _listing(empty)
        listing.focus()
        await pilot.press("g", "G", "ctrl+d", "ctrl+u", "ctrl+f", "ctrl+b")
        await pilot.pause()
        assert listing.index is None

    single = VimListHarness(1)
    async with single.run_test(size=(80, 12)) as pilot:
        listing = _listing(single)
        listing.focus()
        await pilot.press("g", "G", "ctrl+d", "ctrl+f")
        await pilot.pause()
        assert listing.index == 0


def _search_app() -> YTMusicApp:
    search = MagicMock()
    search.search = MagicMock(return_value=SAMPLE_SONGS)
    search.suggest = MagicMock(return_value=[])
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    return make_test_app(search_service=search, playback_service=playback)


async def _search_and_focus_results(pilot: Pilot[None], app: YTMusicApp) -> SongTable:
    app.query_one("#search_input", Input).value = "ambient"
    await pilot.press("enter")
    await app.workers.wait_for_complete()
    await pilot.pause()
    table = app.query_one("#results_table", SongTable)
    table.focus_list()
    await pilot.pause()
    return table


@pytest.mark.asyncio
async def test_i_from_song_table_focuses_search() -> None:
    app = _search_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = await _search_and_focus_results(pilot, app)
        assert table.query_one(VimListView).has_focus
        await pilot.press("i")
        await pilot.pause()
        assert app.query_one("#search_input", Input).has_focus


@pytest.mark.asyncio
async def test_slash_from_song_table_focuses_search() -> None:
    app = _search_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = await _search_and_focus_results(pilot, app)
        assert table.query_one(VimListView).has_focus
        await pilot.press("slash")
        await pilot.pause()
        assert app.query_one("#search_input", Input).has_focus
        assert "/" not in app.query_one("#search_input", Input).value
