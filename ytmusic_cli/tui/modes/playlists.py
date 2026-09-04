"""Playlists mode: local lists for the active profile."""

from typing import TYPE_CHECKING, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, ListView, OptionList
from textual.widgets.option_list import Option

from ytmusic_cli.exceptions import YTMusicError
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Playlist
from ytmusic_cli.tui.modals.confirm import ConfirmModal
from ytmusic_cli.tui.modals.prompt import PromptModal
from ytmusic_cli.tui.widgets.select_list import SelectList
from ytmusic_cli.tui.widgets.song_table import SongRow, SongTable

if TYPE_CHECKING:
    from ytmusic_cli.main import YTMusicApp


class PlaylistsMode(Horizontal):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "new_playlist", "New", show=False),
        Binding("d", "delete_focused", "Delete", show=False),
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

    def compose(self) -> ComposeResult:
        with Vertical(id="playlist_nav"):
            yield SelectList(id="playlist_list")
            yield Label(
                "No playlists. Press n to create one.",
                id="playlists_empty",
            )
        yield SongTable(id="playlist_tracks", allow_delete=True, allow_append=True)

    def reload(self) -> None:
        app = cast("YTMusicApp", self.app)
        user = AppState().current_user.get()
        if app.playlist_service is None or user is None:
            self._playlists = []
            self._render_lists()
            return
        self._playlists = app.playlist_service.list_playlists(user["id"])
        self._render_lists()

    def action_new_playlist(self) -> None:
        self.app.push_screen(PromptModal("New playlist", "Name"), self._on_new_name)

    def action_delete_focused(self) -> None:
        focused = self.app.focused
        if focused is not None and focused.id == "playlist_list":
            playlist = self._current_playlist()
            if playlist is None:
                return
            self.app.push_screen(
                ConfirmModal(f"Delete playlist “{playlist['name']}”?"),
                self._on_confirm_delete_playlist,
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
        app = cast("YTMusicApp", self.app)
        app.play_playlist(playlist["songs"], 0)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, SongRow):
            return
        playlist = self._current_playlist()
        table = self.query_one("#playlist_tracks", SongTable)
        index = table.selected_index()
        if playlist is None or index is None:
            return
        app = cast("YTMusicApp", self.app)
        app.play_playlist(playlist["songs"], index)

    def on_song_table_delete_requested(
        self,
        message: SongTable.DeleteRequested,
    ) -> None:
        message.stop()
        playlist = self._current_playlist()
        app = cast("YTMusicApp", self.app)
        if playlist is None or app.playlist_service is None:
            return
        try:
            app.playlist_service.remove_song(playlist["id"], message.song["video_id"])
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        self.reload()

    def _on_new_name(self, name: str | None) -> None:
        if name is None:
            return
        app = cast("YTMusicApp", self.app)
        user = AppState().current_user.get()
        if app.playlist_service is None or user is None:
            self.notify("Create a profile to use playlists", severity="warning")
            return
        try:
            created = app.playlist_service.create_playlist(user["id"], name)
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        self._selected_id = created["id"]
        self.reload()
        self.notify(f"Created {created['name']}", severity="information")

    def _on_confirm_delete_playlist(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        playlist = self._current_playlist()
        app = cast("YTMusicApp", self.app)
        if playlist is None or app.playlist_service is None:
            return
        try:
            app.playlist_service.delete_playlist(playlist["id"])
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        self._selected_id = None
        self.reload()

    def _current_playlist(self) -> Playlist | None:
        for playlist in self._playlists:
            if playlist["id"] == self._selected_id:
                return playlist
        return None

    def _render_lists(self) -> None:
        option_list = self.query_one("#playlist_list", SelectList)
        option_list.clear_options()
        empty = self.query_one("#playlists_empty", Label)
        empty.display = not self._playlists
        for playlist in self._playlists:
            option_list.add_option(Option(playlist["name"], id=f"pl_{playlist['id']}"))
        if self._playlists and self._selected_id is None:
            self._selected_id = self._playlists[0]["id"]
        self._render_tracks()

    def _render_tracks(self) -> None:
        table = self.query_one("#playlist_tracks", SongTable)
        playlist = self._current_playlist()
        songs = playlist["songs"] if playlist is not None else []
        song = AppState().current_song.get()
        table.set_playing_id(song["video_id"] if song is not None else None)
        table.set_songs(songs)
