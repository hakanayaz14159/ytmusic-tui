"""Yes / no confirmation modal."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmModal(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("n", "cancel", "No", show=False),
        Binding("q", "cancel", "Cancel", show=False),
        Binding("y", "accept", "Yes", show=False),
        Binding("enter", "accept", "Yes", show=False),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_panel"):
            yield Static(self._message)
            yield Static("[y] Yes   [n] No")

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
