"""Application header widget."""

from collections.abc import Callable  # noqa: TC003
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Playlist, Song


class Header(Container):
    """Header widget."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.app_state = AppState()
        self._unsub_song: Callable[[], None] | None = None
        self._unsub_playlist: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static("YTMusic CLI", id="header_title"),
            Static("", id="song_info"),
            Static("", id="playlist_info"),
        )

    def on_mount(self) -> None:
        self._unsub_song = self.app_state.current_song.subscribe(self.update_song_info)
        self._unsub_playlist = self.app_state.current_playlist.subscribe(
            self.update_playlist_info
        )

    def on_unmount(self) -> None:
        if self._unsub_song is not None:
            self._unsub_song()
            self._unsub_song = None
        if self._unsub_playlist is not None:
            self._unsub_playlist()
            self._unsub_playlist = None

    def update_song_info(self, song: Song | None) -> None:
        if song is None:
            self.query_one("#song_info", Static).update("")
        else:
            self.query_one("#song_info", Static).update(f"Song: {song['title']}")

    def update_playlist_info(self, playlist: Playlist | None) -> None:
        if playlist is None:
            self.query_one("#playlist_info", Static).update("")
        else:
            self.query_one("#playlist_info", Static).update(
                f"Playlist: {playlist['name']}"
            )
