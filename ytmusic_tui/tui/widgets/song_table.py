"""Columnar song list with vim motion and play/queue actions."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListItem, ListView

from ytmusic_tui.music.types import Song
from ytmusic_tui.tui.format import (
    SONG_TITLE_WIDTH,
    SONG_UPLOADER_WIDTH,
    format_song_line,
)
from ytmusic_tui.tui.widgets.list_motion import (
    LIST_MOTION_BINDINGS,
    clamp_cursor,
    motion_step,
)


class SongRow(ListItem):
    """List item that carries the associated Song domain object."""

    def __init__(self, song: Song, *, playing: bool = False) -> None:
        super().__init__(Label(format_song_line(song, playing=playing), markup=False))
        self.song = song
        self.set_class(playing, "-playing")


class VimListView(ListView):
    BINDINGS: ClassVar[list[BindingType]] = list(LIST_MOTION_BINDINGS)

    def action_first(self) -> None:
        if len(self):
            self.index = 0

    def action_last(self) -> None:
        count = len(self)
        if count:
            self.index = count - 1

    def action_page_down(self) -> None:
        self._nudge_index(
            motion_step(self.scrollable_content_region.height, half=False)
        )

    def action_page_up(self) -> None:
        self._nudge_index(
            -motion_step(self.scrollable_content_region.height, half=False)
        )

    def action_half_page_down(self) -> None:
        self._nudge_index(motion_step(self.scrollable_content_region.height, half=True))

    def action_half_page_up(self) -> None:
        self._nudge_index(
            -motion_step(self.scrollable_content_region.height, half=True)
        )

    def _nudge_index(self, delta: int) -> None:
        index = clamp_cursor(self.index, delta, len(self))
        if index is not None:
            self.index = index


class SongTable(Vertical):
    """Title / uploader / duration list used by Search, Queue, and Playlists."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "append_selected", show=False),
        Binding("d", "delete_selected", show=False),
        Binding("i", "focus_search", show=False),
        Binding("slash", "focus_search", show=False),
    ]

    class AppendRequested(Message):
        def __init__(self, song: Song) -> None:
            super().__init__()
            self.song = song

    class DeleteRequested(Message):
        def __init__(self, table: "SongTable", index: int, song: Song) -> None:
            super().__init__()
            self.table = table
            self.index = index
            self.song = song

    class FocusSearchRequested(Message):
        pass

    def __init__(
        self,
        *,
        allow_delete: bool = False,
        allow_append: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.allow_delete = allow_delete
        self.allow_append = allow_append
        self._songs: list[Song] = []
        self._playing_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(
            f"  {'Title':<{SONG_TITLE_WIDTH}}  "
            f"{'Uploader':<{SONG_UPLOADER_WIDTH}}  Time",
            id="song_table_header",
        )
        yield VimListView()

    def has_songs(self) -> bool:
        return bool(self._songs)

    def set_songs(self, songs: list[Song]) -> None:
        self._songs = list(songs)
        self._rebuild()

    def set_playing_id(self, video_id: str | None) -> None:
        if self._playing_id == video_id:
            return
        self._playing_id = video_id
        self._rebuild()

    def get_selected_song(self) -> Song | None:
        item = self.query_one(VimListView).highlighted_child
        if isinstance(item, SongRow):
            return item.song
        return None

    def selected_index(self) -> int | None:
        return self.query_one(VimListView).index

    def set_selected_index(self, index: int) -> None:
        if not self._songs:
            return
        song_list = self.query_one(VimListView)
        song_list.index = max(0, min(index, len(self._songs) - 1))

    def focus_list(self) -> None:
        self.query_one(VimListView).focus()

    def action_append_selected(self) -> None:
        if not self.allow_append:
            return
        song = self.get_selected_song()
        if song is not None:
            self.post_message(self.AppendRequested(song))

    def action_delete_selected(self) -> None:
        if not self.allow_delete:
            return
        song = self.get_selected_song()
        index = self.selected_index()
        if song is not None and index is not None:
            self.post_message(self.DeleteRequested(self, index, song))

    def action_focus_search(self) -> None:
        self.post_message(self.FocusSearchRequested())

    def _rebuild(self) -> None:
        song_list = self.query_one(VimListView)
        previous = song_list.index
        was_focused = song_list.has_focus
        song_list.clear()
        for song in self._songs:
            playing = (
                self._playing_id is not None and song["video_id"] == self._playing_id
            )
            song_list.append(SongRow(song, playing=playing))
        if self._songs:
            song_list.index = (
                previous if previous is not None and previous < len(self._songs) else 0
            )
        if was_focused:
            song_list.focus()
