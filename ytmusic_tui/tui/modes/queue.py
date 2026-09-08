"""Queue mode: the upcoming play list."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label

from ytmusic_tui.music.state import AppState
from ytmusic_tui.tui.app import ytmusic_app
from ytmusic_tui.tui.widgets.queue_list import QueueList

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.app import ComposeResult

    from ytmusic_tui.music.types import Playlist, Song


class QueueMode(Vertical):
    can_focus = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("o", "open_playlist", show=False),
        Binding("n", "save_as_playlist", show=False),
        Binding("w", "overwrite_playlist", show=False),
    ]

    class QueueChanged(Message):
        pass

    class WorkingChanged(Message):
        pass

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._state = AppState()
        self._unsub_queue: Callable[[], None] | None = None
        self._unsub_working: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        yield Label("", id="queue_working", markup=False)
        yield Label(
            "Queue is empty. Press a on a search result to add tracks.",
            id="queue_empty",
        )
        yield QueueList(id="queue_table")

    def on_mount(self) -> None:
        self._unsub_queue = self._state.queue.subscribe(self._on_queue)
        self._unsub_working = self._state.current_playlist.subscribe(self._on_working)
        self._sync_empty()
        self._sync_working()

    def on_unmount(self) -> None:
        if self._unsub_queue is not None:
            self._unsub_queue()
            self._unsub_queue = None
        if self._unsub_working is not None:
            self._unsub_working()
            self._unsub_working = None

    def reload(self) -> None:
        pass

    def activate(self) -> None:
        self._sync_empty()
        self._sync_working()
        table = self.query_one("#queue_table", QueueList)
        if table.has_songs():
            table.activate_list()
            return
        self.focus()

    def action_open_playlist(self) -> None:
        ytmusic_app(self.app).prompt_open_working_playlist()

    def action_save_as_playlist(self) -> None:
        ytmusic_app(self.app).prompt_save_queue_as_playlist()

    def action_overwrite_playlist(self) -> None:
        ytmusic_app(self.app).prompt_overwrite_working_playlist()

    def _on_queue(self, _queue: list[Song]) -> None:
        if self.is_mounted:
            self.post_message(self.QueueChanged())

    def _on_working(self, _playlist: Playlist | None) -> None:
        if self.is_mounted:
            self.post_message(self.WorkingChanged())

    def on_queue_mode_queue_changed(self, _message: QueueChanged) -> None:
        self._sync_empty()

    def on_queue_mode_working_changed(self, _message: WorkingChanged) -> None:
        self._sync_working()

    def _sync_working(self) -> None:
        label = self.query_one("#queue_working", Label)
        working = self._state.current_playlist.get()
        if working is None:
            label.update("")
            label.display = False
            return
        label.update(f"Working: {working['name']}")
        label.display = True

    def _sync_empty(self) -> None:
        is_empty = len(self._state.queue.get()) == 0
        self.query_one("#queue_empty", Label).display = is_empty
        self.query_one("#queue_table", QueueList).display = not is_empty
