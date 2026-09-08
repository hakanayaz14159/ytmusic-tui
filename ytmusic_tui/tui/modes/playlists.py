"""Playlists mode: local lists for the active profile."""

from functools import partial
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Label, ListView, OptionList
from textual.widgets.option_list import Option

from ytmusic_tui.exceptions import YTMusicError
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import Playlist, Song
from ytmusic_tui.tui.access import ytmusic_app
from ytmusic_tui.tui.modals.confirm import ConfirmModal
from ytmusic_tui.tui.modals.prompt import PromptModal
from ytmusic_tui.tui.widgets.select_list import SelectList
from ytmusic_tui.tui.widgets.song_table import SongRow, SongTable

if TYPE_CHECKING:
    from collections.abc import Callable


class PlaylistsMode(Horizontal):
    class PlayingChanged(Message):
        def __init__(self, song: Song | None) -> None:
            super().__init__()
            self.song = song

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "new_playlist", "New", show=False),
        Binding("d", "delete_focused", "Delete", show=False),
        Binding("right,l", "focus_tracks", "Tracks", show=False),
        Binding("left,h", "focus_playlists", "Playlists", show=False),
    ]

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._playlists: list[Playlist] = []
        self._selected_id: int | None = None
        self._load_generation = 0
        self._unsub_song: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="playlist_nav"):
            yield SelectList(id="playlist_list", markup=False)
            yield Label(
                "No playlists. Press n to create one.",
                id="playlists_empty",
            )
        yield SongTable(id="playlist_tracks", allow_delete=True, allow_append=True)

    def on_mount(self) -> None:
        self._unsub_song = AppState().current_song.subscribe(self._on_song)

    def on_unmount(self) -> None:
        self._load_generation += 1
        if self._unsub_song is not None:
            self._unsub_song()
            self._unsub_song = None

    @work(thread=True, exclusive=True, group="playlists")
    def reload(self) -> None:
        self._load_generation += 1
        generation = self._load_generation
        app = ytmusic_app(self.app)
        user = AppState().current_user.get()
        user_id = user["id"] if user is not None else None
        if user is None:
            app.call_from_thread(self._apply_playlists, generation, user_id, [])
            return
        try:
            playlists = app.playlist_service.list_playlists(user["id"])
        except YTMusicError as err:
            app.call_from_thread(self._on_reload_error, generation, user_id, str(err))
            return
        app.call_from_thread(self._apply_playlists, generation, user_id, playlists)

    def _is_current_load(self, generation: int, user_id: int | None) -> bool:
        if not self.is_mounted or generation != self._load_generation:
            return False
        current = AppState().current_user.get()
        current_id = current["id"] if current is not None else None
        return current_id == user_id

    def _on_reload_error(
        self, generation: int, user_id: int | None, message: str
    ) -> None:
        if not self._is_current_load(generation, user_id):
            return
        self.notify(message, severity="error")

    def _apply_playlists(
        self, generation: int, user_id: int | None, playlists: list[Playlist]
    ) -> None:
        if not self._is_current_load(generation, user_id):
            return
        self._playlists = playlists
        self._render_lists()

    def activate(self) -> None:
        self.action_focus_playlists()

    def action_focus_playlists(self) -> None:
        self.query_one("#playlist_list", SelectList).focus()

    def action_focus_tracks(self) -> None:
        self.query_one("#playlist_tracks", SongTable).focus_list()

    def action_new_playlist(self) -> None:
        self.app.push_screen(PromptModal("New playlist", "Name"), self._on_new_name)

    def action_delete_focused(self) -> None:
        focused = self.app.focused
        if focused is not None and focused.id == "playlist_list":
            playlist = self._current_playlist()
            if playlist is None:
                return
            self.app.push_screen(
                ConfirmModal(f'Delete playlist "{playlist["name"]}"?'),
                partial(self._on_confirm_delete_playlist, playlist),
            )

    def on_option_list_option_highlighted(
        self,
        event: OptionList.OptionHighlighted,
    ) -> None:
        if event.option.id is None:
            return
        self._selected_id = int(event.option.id.removeprefix("pl_"))
        self._render_tracks()

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        if event.option.id is None:
            return
        self._selected_id = int(event.option.id.removeprefix("pl_"))
        playlist = self._current_playlist()
        if playlist is None:
            return
        app = ytmusic_app(self.app)
        app.load_playlist_into_queue(playlist["id"], play=True, start_index=0)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, SongRow):
            return
        playlist = self._current_playlist()
        table = self.query_one("#playlist_tracks", SongTable)
        index = table.selected_index()
        if playlist is None or index is None:
            return
        app = ytmusic_app(self.app)
        app.load_playlist_into_queue(playlist["id"], play=True, start_index=index)

    def on_song_table_delete_requested(
        self,
        message: SongTable.DeleteRequested,
    ) -> None:
        message.stop()
        playlist = self._current_playlist()
        if playlist is None:
            return
        self._remove_playlist_song(playlist["id"], message.song["video_id"])

    def _on_new_name(self, name: str | None) -> None:
        if name is None:
            return
        user = AppState().current_user.get()
        if user is None:
            self.notify("Create a profile to use playlists", severity="warning")
            return
        self._create_playlist(user["id"], name)

    def _on_confirm_delete_playlist(
        self,
        playlist: Playlist,
        confirmed: bool | None,
    ) -> None:
        if not confirmed:
            return
        self._delete_playlist(playlist)

    @work(thread=True, exclusive=True, group="playlists")
    def _create_playlist(self, user_id: int, name: str) -> None:
        app = ytmusic_app(self.app)
        try:
            created = app.playlist_service.create_playlist(user_id, name)
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._on_playlist_created, created)

    def _on_playlist_created(self, created: Playlist) -> None:
        self._selected_id = created["id"]
        self.reload()
        self.notify(f"Created {created['name']}", severity="information")

    @work(thread=True, exclusive=True, group="playlists")
    def _delete_playlist(self, playlist: Playlist) -> None:
        app = ytmusic_app(self.app)
        try:
            app.playlist_service.delete_playlist(playlist["id"])
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._on_playlist_deleted, playlist)

    def _on_playlist_deleted(self, playlist: Playlist) -> None:
        self._selected_id = None
        self.reload()
        self.notify(f"Deleted {playlist['name']}", severity="information")

    @work(thread=True, exclusive=True, group="playlists")
    def _remove_playlist_song(self, playlist_id: int, video_id: str) -> None:
        app = ytmusic_app(self.app)
        try:
            app.playlist_service.remove_song(playlist_id, video_id)
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self.reload)

    def _current_playlist(self) -> Playlist | None:
        for playlist in self._playlists:
            if playlist["id"] == self._selected_id:
                return playlist
        return None

    def _on_song(self, song: Song | None) -> None:
        if self.is_mounted:
            self.post_message(self.PlayingChanged(song))

    def on_playlists_mode_playing_changed(self, message: PlayingChanged) -> None:
        table = self.query_one("#playlist_tracks", SongTable)
        song = message.song
        table.set_playing_id(song["video_id"] if song is not None else None)

    def _render_lists(self) -> None:
        option_list = self.query_one("#playlist_list", SelectList)
        option_list.clear_options()
        empty = self.query_one("#playlists_empty", Label)
        empty.display = not self._playlists
        for playlist in self._playlists:
            option_list.add_option(Option(playlist["name"], id=f"pl_{playlist['id']}"))
        if self._playlists and self._selected_id is None:
            self._selected_id = self._playlists[0]["id"]
        if self._playlists:
            for index, playlist in enumerate(self._playlists):
                if playlist["id"] == self._selected_id:
                    option_list.highlighted = index
                    break
        self._render_tracks()

    def _render_tracks(self) -> None:
        table = self.query_one("#playlist_tracks", SongTable)
        playlist = self._current_playlist()
        songs = playlist["songs"] if playlist is not None else []
        song = AppState().current_song.get()
        table.set_playing_id(song["video_id"] if song is not None else None)
        table.set_songs(songs)
