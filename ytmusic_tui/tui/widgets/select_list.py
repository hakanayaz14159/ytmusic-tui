"""OptionList with vim motion bindings."""

from typing import ClassVar

from textual.binding import BindingType
from textual.widgets import OptionList

from ytmusic_tui.tui.widgets.list_motion import (
    LIST_MOTION_BINDINGS,
    clamp_cursor,
    motion_step,
)


class SelectList(OptionList):
    BINDINGS: ClassVar[list[BindingType]] = list(LIST_MOTION_BINDINGS)

    def action_half_page_down(self) -> None:
        self._nudge_highlighted(
            motion_step(self.scrollable_content_region.height, half=True)
        )

    def action_half_page_up(self) -> None:
        self._nudge_highlighted(
            -motion_step(self.scrollable_content_region.height, half=True)
        )

    def _nudge_highlighted(self, delta: int) -> None:
        index = clamp_cursor(self.highlighted, delta, self.option_count)
        if index is not None:
            self.highlighted = index
