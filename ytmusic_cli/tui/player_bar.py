"""Persistent mini-player bar widget."""

from collections.abc import Callable  # noqa: TC003

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackState, PlaybackStatus, Song

_STATUS_GLYPHS: dict[PlaybackStatus, str] = {
    PlaybackStatus.PLAYING: "▶",
    PlaybackStatus.PAUSED: "⏸",
    PlaybackStatus.STOPPED: "■",
}


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


class PlayerBar(Static):
    """Docked mini-player showing playback status, track, progress, and volume."""

    class StateUpdated(Message):
        """Dispatched to marshal AppState updates onto Textual's event loop."""

        def __init__(self, song: Song | None, playback: PlaybackState) -> None:
            super().__init__()
            self.song = song
            self.playback = playback

    DEFAULT_CSS = """
    PlayerBar {
        dock: bottom;
        width: 100%;
        height: 3;
        background: $panel;
        color: $foreground;
        border-top: solid $primary;
        padding: 0 1;
    }

    PlayerBar > Horizontal {
        width: 100%;
        height: 100%;
        align: left middle;
    }

    PlayerBar #player_status {
        width: 3;
        content-align: center middle;
    }

    PlayerBar #player_track {
        width: 1fr;
        padding: 0 1;
    }

    PlayerBar #player_progress {
        width: auto;
        padding: 0 1;
    }

    PlayerBar #player_volume {
        width: auto;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._app_state = AppState()
        self._unsub_song: Callable[[], None] | None = None
        self._unsub_playback: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static("■", id="player_status"),
            Static("[No track playing]", id="player_track"),
            Static("", id="player_progress"),
            Static("[Vol: 80%]", id="player_volume"),
        )

    def on_mount(self) -> None:
        self._unsub_song = self._app_state.current_song.subscribe(self._on_song_changed)
        self._unsub_playback = self._app_state.playback_state.subscribe(
            self._on_playback_changed
        )
        self._refresh(
            self._app_state.current_song.get(),
            self._app_state.playback_state.get(),
        )

    def on_unmount(self) -> None:
        if self._unsub_song is not None:
            self._unsub_song()
            self._unsub_song = None
        if self._unsub_playback is not None:
            self._unsub_playback()
            self._unsub_playback = None

    def _on_song_changed(self, song: Song | None) -> None:
        if self.is_mounted:
            self.post_message(
                self.StateUpdated(song, self._app_state.playback_state.get())
            )

    def _on_playback_changed(self, playback: PlaybackState) -> None:
        if self.is_mounted:
            self.post_message(
                self.StateUpdated(self._app_state.current_song.get(), playback)
            )

    def on_player_bar_state_updated(self, message: StateUpdated) -> None:
        self._refresh(message.song, message.playback)

    def _refresh(self, song: Song | None, playback: PlaybackState) -> None:
        if not self.is_mounted:
            return
        glyph = _STATUS_GLYPHS[playback["status"]]
        track = (
            f"{song['title']} - {song['artist']}"
            if song is not None
            else "[No track playing]"
        )
        volume = f"[Vol: {playback['volume']}%]"
        progress = ""
        if playback["duration"] > 0:
            progress = (
                f"{_format_time(playback['position'])} / "
                f"{_format_time(float(playback['duration']))}"
            )

        try:
            self.query_one("#player_status", Static).update(glyph)
            self.query_one("#player_track", Static).update(track)
            self.query_one("#player_progress", Static).update(progress)
            self.query_one("#player_volume", Static).update(volume)
        except Exception:
            pass
