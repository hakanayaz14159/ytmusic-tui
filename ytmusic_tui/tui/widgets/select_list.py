"""OptionList with vim motion bindings."""

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import OptionList


class SelectList(OptionList):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]
