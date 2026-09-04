"""Always-visible now-playing strip."""

from collections.abc import Callable  # noqa: TC003

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static

from ytmusic_cli.consts import COMPACT_HEIGHT_ROWS
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackState, PlaybackStatus, Song
from ytmusic_cli.tui.format import (
    format_duration,
    format_progress_bar,
    format_volume_gauge,
)

_STATUS_GLYPHS: dict[PlaybackStatus, str] = {
    PlaybackStatus.PLAYING: "▶",
    PlaybackStatus.PAUSED: "⏸",
    PlaybackStatus.STOPPED: "■",
}


class NowPlaying(Vertical):
    """Two-line now-playing status; collapses to one line on short terminals."""

    class StateUpdated(Message):
        def __init__(self, song: Song | None, playback: PlaybackState) -> None:
            super().__init__()
            self.song = song
            self.playback = playback

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
        yield Static("■  [No track playing]", id="np_title")
        yield Static("", id="np_detail")

    def on_mount(self) -> None:
        self._unsub_song = self._app_state.current_song.subscribe(self._on_song)
        self._unsub_playback = self._app_state.playback_state.subscribe(
            self._on_playback
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

    def on_resize(self) -> None:
        self.set_class(self.app.size.height < COMPACT_HEIGHT_ROWS, "-compact")
        self._refresh(
            self._app_state.current_song.get(),
            self._app_state.playback_state.get(),
        )

    def _on_song(self, song: Song | None) -> None:
        if self.is_mounted:
            self.post_message(
                self.StateUpdated(song, self._app_state.playback_state.get())
            )

    def _on_playback(self, playback: PlaybackState) -> None:
        if self.is_mounted:
            self.post_message(
                self.StateUpdated(self._app_state.current_song.get(), playback)
            )

    def on_now_playing_state_updated(self, message: StateUpdated) -> None:
        self._refresh(message.song, message.playback)

    def _refresh(self, song: Song | None, playback: PlaybackState) -> None:
        if not self.is_mounted:
            return
        glyph = _STATUS_GLYPHS[playback["status"]]
        if song is None:
            title = f"{glyph}  [No track playing]"
            detail = f"{format_volume_gauge(playback['volume'])}  {playback['volume']}%"
        else:
            artist = song["artist"] or "Unknown Artist"
            title = f"{glyph}  {song['title']}  —  {artist}"
            progress = format_progress_bar(playback["position"], playback["duration"])
            clock = (
                f"{format_duration(playback['position'])} / "
                f"{format_duration(playback['duration'])}"
            )
            gauge = format_volume_gauge(playback["volume"])
            detail = f"{progress}  {clock}            {gauge}  {playback['volume']}%"
        self.query_one("#np_title", Static).update(title)
        self.query_one("#np_detail", Static).update(detail)
