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
        stream = self._source.get_stream(song["video_id"])
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
        elif status == PlaybackStatus.STOPPED:
            song = self._state.current_song.get()
            if song is not None:
                self.play_song(song)

    def stop(self) -> None:
        self._player.stop()
        self._state.current_song.set(None)
        self._patch_playback(
            status=PlaybackStatus.STOPPED,
            position=0.0,
            duration=0,
        )

    def volume_up(self) -> None:
        self._adjust_volume(_VOLUME_STEP)

    def volume_down(self) -> None:
        self._adjust_volume(-_VOLUME_STEP)

    def sync_playback(self) -> None:
        current = self._state.playback_state.get()
        if current["status"] != PlaybackStatus.PLAYING:
            return
        if self._player.has_ended():
            self._patch_playback(status=PlaybackStatus.STOPPED)
            return
        position = self._player.get_position()
        if int(position) == int(current["position"]):
            return
        self._patch_playback(position=position)

    def _adjust_volume(self, delta: int) -> None:
        current = self._state.playback_state.get()
        new_volume = max(0, min(100, current["volume"] + delta))
        self._player.set_volume(new_volume)
        self._patch_playback(volume=new_volume)

    def _set_status(self, status: PlaybackStatus) -> None:
        self._patch_playback(status=status)

    def _patch_playback(
        self,
        *,
        status: PlaybackStatus | None = None,
        volume: int | None = None,
        position: float | None = None,
        duration: int | None = None,
    ) -> None:
        current = self._state.playback_state.get()
        self._state.playback_state.set(
            PlaybackState(
                status=current["status"] if status is None else status,
                volume=current["volume"] if volume is None else volume,
                position=current["position"] if position is None else position,
                duration=current["duration"] if duration is None else duration,
            )
        )
