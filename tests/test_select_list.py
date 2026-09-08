"""Pilot tests for SelectList vim motion."""

import pytest
from textual.app import App, ComposeResult

from ytmusic_tui.tui.widgets.select_list import SelectList

_ITEM_COUNT = 40


class SelectListHarness(App[None]):
    def __init__(self, count: int = _ITEM_COUNT) -> None:
        super().__init__()
        self._count = count

    def compose(self) -> ComposeResult:
        yield SelectList(
            *[f"item-{index}" for index in range(self._count)],
            id="select_list",
        )


def _listing(app: App[None]) -> SelectList:
    return app.query_one("#select_list", SelectList)


@pytest.mark.asyncio
async def test_select_list_g_and_G_jump_to_ends() -> None:
    app = SelectListHarness()
    async with app.run_test(size=(80, 12)) as pilot:
        listing = _listing(app)
        listing.focus()
        listing.highlighted = 12
        await pilot.press("g")
        await pilot.pause()
        assert listing.highlighted == 0

        await pilot.press("G")
        await pilot.pause()
        assert listing.highlighted == _ITEM_COUNT - 1


@pytest.mark.asyncio
async def test_select_list_page_keys_move_and_clamp_highlight() -> None:
    app = SelectListHarness()
    async with app.run_test(size=(80, 12)) as pilot:
        listing = _listing(app)
        listing.focus()
        listing.highlighted = 0
        await pilot.press("ctrl+d")
        await pilot.pause()
        half_down = listing.highlighted
        assert half_down is not None and half_down > 0

        listing.highlighted = 0
        await pilot.press("ctrl+f")
        await pilot.pause()
        page_down = listing.highlighted
        assert page_down is not None and page_down >= half_down

        listing.highlighted = 0
        await pilot.press("pagedown")
        await pilot.pause()
        assert listing.highlighted == page_down

        listing.highlighted = _ITEM_COUNT - 1
        await pilot.press("ctrl+u")
        await pilot.pause()
        half_up = listing.highlighted
        assert half_up is not None and half_up < _ITEM_COUNT - 1

        listing.highlighted = _ITEM_COUNT - 1
        await pilot.press("ctrl+b")
        await pilot.pause()
        page_up = listing.highlighted
        assert page_up is not None and page_up <= half_up

        listing.highlighted = 0
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert listing.highlighted == 0

        listing.highlighted = _ITEM_COUNT - 1
        await pilot.press("ctrl+f")
        await pilot.pause()
        assert listing.highlighted == _ITEM_COUNT - 1


@pytest.mark.asyncio
async def test_select_list_empty_and_single_item_do_not_crash() -> None:
    empty = SelectListHarness(0)
    async with empty.run_test(size=(80, 12)) as pilot:
        listing = _listing(empty)
        listing.focus()
        await pilot.press("g", "G", "ctrl+d", "ctrl+u", "ctrl+f", "ctrl+b")
        await pilot.pause()
        assert listing.highlighted is None

    single = SelectListHarness(1)
    async with single.run_test(size=(80, 12)) as pilot:
        listing = _listing(single)
        listing.focus()
        await pilot.press("g", "G", "ctrl+d", "ctrl+f")
        await pilot.pause()
        assert listing.highlighted == 0
