"""Playback orchestration: stream resolution, player control, and queue."""

import logging

from ytmusic_tui.consts import MAX_VOLUME, PLAYBACK_STALL_TICKS
from ytmusic_tui.exceptions import PlaybackError, ValidationError
from ytmusic_tui.music.ports import AudioPlayerProtocol, MusicSourceProtocol
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import (
    AudioStream,
    PlaybackState,
    PlaybackStatus,
    PlaybackTick,
    PlaybackTickAction,
    Song,
)

logger = logging.getLogger(__name__)

_VOLUME_STEP = 5


class PlaybackService:
    """Orchestrates stream resolution, player control, queue, and AppState.

    Workers resolve and prepare streams; the main thread commits their state.
    Callers serialize engine preparation and discard stale prepared streams.
    """

    def __init__(
        self,
        player: AudioPlayerProtocol,
        source: MusicSourceProtocol,
        state: AppState,
    ) -> None:
        self._player = player
        self._source = source
        self._state = state
        self._stall_ticks = 0
        self._engine_started = False

    def resolve_stream(self, song: Song) -> AudioStream:
        logger.info(
            "resolve_stream video_id=%s title=%s",
            song["video_id"],
            song["title"],
        )
        return self._source.get_stream(song["video_id"])

    def start_stream(self, song: Song, stream: AudioStream) -> None:
        self.prepare_stream(stream)
        self.commit_stream(song)

    def prepare_stream(self, stream: AudioStream) -> None:
        """Start the audio engine from a worker without publishing UI state."""
        try:
            self._player.play(stream)
            self._player.set_volume(self._state.playback_state.get()["volume"])
        except PlaybackError:
            try:
                self.discard_stream()
            except PlaybackError:
                logger.exception("failed to clean up an unsuccessful stream")
            raise

    def discard_stream(self) -> None:
        """Stop a prepared engine stream without publishing UI state."""
        self._player.stop()

    def commit_stream(self, song: Song) -> None:
        """Publish a successfully prepared stream on the UI thread."""
        logger.info(
            "start_stream video_id=%s title=%s",
            song["video_id"],
            song["title"],
        )
        self._align_queue_for_play(song)
        current = self._state.playback_state.get()
        self._stall_ticks = 0
        self._engine_started = False
        self._state.current_song.set(song)
        self._state.playback_state.set(
            PlaybackState(
                status=PlaybackStatus.PLAYING,
                volume=current["volume"],
                position=0.0,
                duration=song["duration"],
            )
        )

    def enqueue(self, song: Song) -> None:
        logger.info("enqueue video_id=%s title=%s", song["video_id"], song["title"])
        self._state.queue.set([*self._state.queue.get(), song])

    def load_queue(self, songs: list[Song]) -> Song:
        current = self._state.current_song.get()
        index = 0
        if current is not None:
            for position, item in enumerate(songs):
                if item["video_id"] == current["video_id"]:
                    index = position
                    break
        return self.set_queue(songs, index)

    def set_queue(self, songs: list[Song], start_index: int = 0) -> Song:
        if not songs:
            logger.warning("set_queue rejected empty playlist")
            raise ValidationError("Playlist is empty")
        index = max(0, min(start_index, len(songs) - 1))
        self._state.queue.set(list(songs))
        self._state.queue_index.set(index)
        logger.info(
            "set_queue count=%s index=%s video_id=%s",
            len(songs),
            index,
            songs[index]["video_id"],
        )
        return songs[index]

    def advance_to_next(self) -> Song | None:
        queue = self._state.queue.get()
        next_index = self._state.queue_index.get() + 1
        if 0 <= next_index < len(queue):
            self._state.queue_index.set(next_index)
            logger.info(
                "advance_to_next index=%s video_id=%s",
                next_index,
                queue[next_index]["video_id"],
            )
            return queue[next_index]
        logger.info("advance_to_next exhausted")
        if self._state.playback_state.get()["status"] != PlaybackStatus.STOPPED:
            self.discard_stream()
            self._patch_playback(status=PlaybackStatus.STOPPED)
        return None

    def advance_to_previous(self) -> Song | None:
        queue = self._state.queue.get()
        prev_index = self._state.queue_index.get() - 1
        if prev_index >= 0 and queue:
            self._state.queue_index.set(prev_index)
            logger.info(
                "advance_to_previous index=%s video_id=%s",
                prev_index,
                queue[prev_index]["video_id"],
            )
            return queue[prev_index]
        logger.info("advance_to_previous at start")
        return None

    def remove_from_queue(self, index: int) -> Song | None:
        queue = list(self._state.queue.get())
        if index < 0 or index >= len(queue):
            logger.warning("remove_from_queue rejected index=%s", index)
            raise ValidationError("Queue index out of range")
        current = self._state.queue_index.get()
        current_song = self._state.current_song.get()
        removing_current = (
            index == current
            and current_song is not None
            and queue[index]["video_id"] == current_song["video_id"]
        )
        was_playing = (
            self._state.playback_state.get()["status"] == PlaybackStatus.PLAYING
        )
        logger.info(
            "remove_from_queue index=%s video_id=%s",
            index,
            queue[index]["video_id"],
        )
        del queue[index]
        self._state.queue.set(queue)
        if removing_current:
            self.stop()
        if not queue:
            self._state.queue_index.set(-1)
            return None
        if index < current:
            self._state.queue_index.set(current - 1)
            return None
        if index == current:
            new_index = min(index, len(queue) - 1)
            self._state.queue_index.set(new_index)
            if removing_current and was_playing:
                return queue[new_index]
        return None

    def toggle(self) -> None:
        current = self._state.playback_state.get()
        status = current["status"]
        if status == PlaybackStatus.PLAYING:
            logger.info("toggle pause")
            self._player.pause()
            self._set_status(PlaybackStatus.PAUSED)
        elif status == PlaybackStatus.PAUSED:
            logger.info("toggle resume")
            self._player.pause()
            self._set_status(PlaybackStatus.PLAYING)

    def stop(self) -> None:
        logger.info("stop")
        self.discard_stream()
        self.commit_stop()

    def commit_stop(self) -> None:
        """Publish an engine stop on the UI thread without touching the player."""
        self._stall_ticks = 0
        self._engine_started = False
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

    def sync_playback(self) -> PlaybackTick:
        current = self._state.playback_state.get()
        if current["status"] != PlaybackStatus.PLAYING:
            return PlaybackTick(PlaybackTickAction.IDLE)
        failure = self._tick_failure()
        if failure is not None:
            return failure
        if self._player.has_ended():
            return self._tick_ended()
        if self._player.is_playing():
            if not self._engine_started:
                song = self._state.current_song.get()
                logger.info(
                    "engine started video_id=%s state=%s",
                    song["video_id"] if song is not None else None,
                    self._player.engine_state(),
                )
            self._stall_ticks = 0
            self._engine_started = True
            if self._player.get_volume() != current["volume"]:
                self._player.set_volume(current["volume"])
            position = self._player.get_position()
            if int(position) != int(current["position"]):
                self._patch_playback(position=position)
            return PlaybackTick(PlaybackTickAction.IDLE)
        self._stall_ticks += 1
        if self._stall_ticks >= PLAYBACK_STALL_TICKS:
            return self._fail_playback("Playback failed to start")
        return PlaybackTick(PlaybackTickAction.IDLE)

    def _tick_failure(self) -> PlaybackTick | None:
        if not self._player.has_failed():
            return None
        return self._fail_playback("Playback failed")

    def _tick_ended(self) -> PlaybackTick:
        self._stall_ticks = 0
        if not self._engine_started:
            return self._fail_playback("Playback failed to start")
        if self._has_next_track():
            return PlaybackTick(PlaybackTickAction.ENDED)
        self.discard_stream()
        self._patch_playback(status=PlaybackStatus.STOPPED)
        return PlaybackTick(PlaybackTickAction.IDLE)

    def _fail_playback(self, message: str) -> PlaybackTick:
        song = self._state.current_song.get()
        logger.error(
            "playback failed message=%s video_id=%s engine_started=%s "
            "stall_ticks=%s has_ended=%s has_failed=%s is_playing=%s "
            "engine_state=%s",
            message,
            song["video_id"] if song is not None else None,
            self._engine_started,
            self._stall_ticks,
            self._player.has_ended(),
            self._player.has_failed(),
            self._player.is_playing(),
            self._player.engine_state(),
        )
        self._player.stop()
        self._stall_ticks = 0
        self._patch_playback(status=PlaybackStatus.STOPPED)
        return PlaybackTick(PlaybackTickAction.FAILED, message)

    def _has_next_track(self) -> bool:
        queue = self._state.queue.get()
        next_index = self._state.queue_index.get() + 1
        return 0 <= next_index < len(queue)

    def _align_queue_for_play(self, song: Song) -> None:
        queue = list(self._state.queue.get())
        if not queue:
            self._state.queue.set([song])
            self._state.queue_index.set(0)
            return
        current_index = self._state.queue_index.get()
        if (
            0 <= current_index < len(queue)
            and queue[current_index]["video_id"] == song["video_id"]
        ):
            return
        for index, item in enumerate(queue):
            if item["video_id"] == song["video_id"]:
                self._state.queue_index.set(index)
                return

    def _adjust_volume(self, delta: int) -> None:
        current = self._state.playback_state.get()
        new_volume = max(0, min(MAX_VOLUME, current["volume"] + delta))
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
