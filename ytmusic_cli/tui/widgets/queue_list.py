"""Song table bound to the playback queue."""

from collections.abc import Callable  # noqa: TC003

from textual.message import Message

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Song
from ytmusic_cli.tui.widgets.song_table import SongTable


class QueueList(SongTable):
    """SongTable that mirrors AppState.queue."""

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
        super().__init__(
            allow_delete=True,
            allow_append=False,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._state = AppState()
        self._unsub_queue: Callable[[], None] | None = None
        self._unsub_song: Callable[[], None] | None = None

    def on_mount(self) -> None:
        self._unsub_queue = self._state.queue.subscribe(self._on_queue)
        self._unsub_song = self._state.current_song.subscribe(self._on_song)
        self._reload()

    def on_unmount(self) -> None:
        if self._unsub_queue is not None:
            self._unsub_queue()
            self._unsub_queue = None
        if self._unsub_song is not None:
            self._unsub_song()
            self._unsub_song = None

    def _on_queue(self, _queue: list[Song]) -> None:
        if self.is_mounted:
            self.post_message(self.QueueChanged())

    def _on_song(self, _song: Song | None) -> None:
        if self.is_mounted:
            self.post_message(self.QueueChanged())

    def on_queue_list_queue_changed(self, _message: QueueChanged) -> None:
        self._reload()

    def activate_list(self) -> None:
        index = self._state.queue_index.get()
        self.set_selected_index(index if index >= 0 else 0)
        self.focus_list()

    def _reload(self) -> None:
        song = self._state.current_song.get()
        self._playing_id = song["video_id"] if song is not None else None
        self.set_songs(self._state.queue.get())
