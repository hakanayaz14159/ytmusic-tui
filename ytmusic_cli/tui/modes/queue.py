"""Queue mode: the upcoming play list."""

from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListView

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Song
from ytmusic_cli.tui.widgets.queue_list import QueueList
from ytmusic_cli.tui.widgets.song_table import SongRow, SongTable

if TYPE_CHECKING:
    from ytmusic_cli.main import YTMusicApp


class QueueMode(Vertical):
    can_focus = True

    class QueueChanged(Message):
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

    def compose(self) -> ComposeResult:
        yield Label(
            "Queue is empty. Press a on a search result to add tracks.",
            id="queue_empty",
        )
        yield QueueList(id="queue_table")

    def on_mount(self) -> None:
        self._unsub_queue = self._state.queue.subscribe(self._on_queue)
        self._sync_empty()

    def on_unmount(self) -> None:
        if self._unsub_queue is not None:
            self._unsub_queue()
            self._unsub_queue = None

    def activate(self) -> None:
        self._sync_empty()
        table = self.query_one("#queue_table", QueueList)
        if table.has_songs():
            table.activate_list()
            return
        self.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, SongRow):
            return
        app = cast("YTMusicApp", self.app)
        app.play_song(event.item.song)

    def on_song_table_delete_requested(
        self,
        message: SongTable.DeleteRequested,
    ) -> None:
        app = cast("YTMusicApp", self.app)
        app.remove_from_queue(message.index)
        message.stop()

    def _on_queue(self, _queue: list[Song]) -> None:
        if self.is_mounted:
            self.post_message(self.QueueChanged())

    def on_queue_mode_queue_changed(self, _message: QueueChanged) -> None:
        self._sync_empty()

    def _sync_empty(self) -> None:
        is_empty = len(self._state.queue.get()) == 0
        self.query_one("#queue_empty", Label).display = is_empty
        self.query_one("#queue_table", QueueList).display = not is_empty
