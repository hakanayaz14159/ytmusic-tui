"""Application services for search and playback workflows."""

from ytmusic_cli.exceptions import ValidationError
from ytmusic_cli.music.ports import AudioPlayerProtocol, MusicSourceProtocol
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackState, PlaybackStatus, Song

_VOLUME_STEP = 5


class SearchService:
    """Delegates music search to a MusicSourceProtocol adapter."""

    def __init__(self, source: MusicSourceProtocol) -> None:
        self._source = source

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        if not query.strip():
            raise ValidationError("Search query must not be empty")
        return self._source.search(query, max_results=max_results)


class PlaybackService:
    """Orchestrates stream resolution, player control, and AppState updates."""

    def __init__(
        self,
        player: AudioPlayerProtocol,
        source: MusicSourceProtocol,
        state: AppState,
    ) -> None:
        self._player = player
        self._source = source
        self._state = state

    def play_song(self, song: Song) -> None:
        stream = self._source.get_stream(song["url"])
        self._player.play(stream)
        current = self._state.playback_state.get()
        self._player.set_volume(current["volume"])
        self._state.current_song.set(song)
        self._state.playback_state.set(
            PlaybackState(
                status=PlaybackStatus.PLAYING,
                volume=current["volume"],
                position=0.0,
                duration=song["duration"],
            )
        )

    def toggle(self) -> None:
        current = self._state.playback_state.get()
        status = current["status"]
        if status == PlaybackStatus.PLAYING:
            self._player.pause()
            self._set_status(PlaybackStatus.PAUSED)
        elif status == PlaybackStatus.PAUSED:
            # VLC pause() toggles; Protocol has no separate resume.
            self._player.pause()
            self._set_status(PlaybackStatus.PLAYING)

    def stop(self) -> None:
        self._player.stop()
        self._state.current_song.set(None)
        current = self._state.playback_state.get()
        self._state.playback_state.set(
            PlaybackState(
                status=PlaybackStatus.STOPPED,
                volume=current["volume"],
                position=0.0,
                duration=0,
            )
        )

    def volume_up(self) -> None:
        self._adjust_volume(_VOLUME_STEP)

    def volume_down(self) -> None:
        self._adjust_volume(-_VOLUME_STEP)

    def _adjust_volume(self, delta: int) -> None:
        current = self._state.playback_state.get()
        new_volume = max(0, min(100, current["volume"] + delta))
        self._player.set_volume(new_volume)
        self._state.playback_state.set(
            PlaybackState(
                status=current["status"],
                volume=new_volume,
                position=current["position"],
                duration=current["duration"],
            )
        )

    def _set_status(self, status: PlaybackStatus) -> None:
        current = self._state.playback_state.get()
        self._state.playback_state.set(
            PlaybackState(
                status=status,
                volume=current["volume"],
                position=current["position"],
                duration=current["duration"],
            )
        )
