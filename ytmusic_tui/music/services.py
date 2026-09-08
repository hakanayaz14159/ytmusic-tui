"""Application services for search, playback, accounts, playlists, and settings."""

import logging

from ytmusic_tui.consts import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SUGGEST_LIMIT,
    DEFAULT_USERNAME,
    DEFAULT_VOLUME,
    MAX_SEARCH_LIMIT,
    MAX_VOLUME,
    MIN_SEARCH_LIMIT,
    MIN_SUGGEST_CHARS,
    PLAYBACK_STALL_TICKS,
)
from ytmusic_tui.exceptions import PlaybackError, ValidationError
from ytmusic_tui.music.ports import (
    AudioPlayerProtocol,
    MusicSourceProtocol,
    PlaylistRepositoryProtocol,
    UserRepositoryProtocol,
)
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import (
    AudioStream,
    PlaybackState,
    PlaybackStatus,
    PlaybackTick,
    PlaybackTickAction,
    Playlist,
    Song,
    User,
    UserSettings,
)

logger = logging.getLogger(__name__)

_VOLUME_STEP = 5


class SearchService:
    """Delegates music search to a MusicSourceProtocol adapter."""

    def __init__(self, source: MusicSourceProtocol) -> None:
        self._source = source

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        if not query.strip():
            logger.warning("search rejected empty query")
            raise ValidationError("Search query must not be empty")
        return self._source.search(query, max_results=max_results)

    def suggest(
        self, query: str, max_results: int = DEFAULT_SUGGEST_LIMIT
    ) -> list[str]:
        cleaned = query.strip()
        if len(cleaned) < MIN_SUGGEST_CHARS:
            return []
        return self._source.suggest(cleaned, max_results=max_results)


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


class AccountService:
    """Local profile create / select / delete."""

    def __init__(
        self,
        users: UserRepositoryProtocol,
        state: AppState,
    ) -> None:
        self._users = users
        self._state = state

    def ensure_default_user(self) -> User:
        local = self._users.get_by_username(DEFAULT_USERNAME)
        if local is not None:
            return local
        existing = self._users.list_users()
        if len(existing) == 1:
            return existing[0]
        return self._users.create_user(DEFAULT_USERNAME)

    def list_users(self) -> list[User]:
        return self._users.list_users()

    def create_user(self, username: str) -> User:
        cleaned = username.strip()
        if not cleaned:
            logger.warning("profile create rejected empty name")
            raise ValidationError("Profile name must not be empty")
        user = self._users.create_user(cleaned)
        logger.info("profile created id=%s username=%s", user["id"], user["username"])
        return user

    def select_user(self, user_id: int) -> User:
        user = self._users.get_user(user_id)
        if user is None:
            logger.warning("profile select missing id=%s", user_id)
            raise ValidationError("Profile not found")
        logger.info("profile selected id=%s username=%s", user["id"], user["username"])
        current = self._state.current_user.get()
        if current is None or current["id"] != user_id:
            self._state.current_playlist.set(None)
        self._state.current_user.set(user)
        playback = self._state.playback_state.get()
        if playback["status"] == PlaybackStatus.STOPPED:
            self._state.playback_state.set(
                {**playback, "volume": user["default_volume"]}
            )
        return user

    def delete_user(self, user_id: int) -> None:
        users = self._users.list_users()
        if len(users) <= 1:
            logger.warning("profile delete rejected last id=%s", user_id)
            raise ValidationError("Cannot delete the last profile")
        logger.info("profile deleted id=%s", user_id)
        self._users.delete_user(user_id)
        current = self._state.current_user.get()
        if current is not None and current["id"] == user_id:
            remaining = self._users.list_users()
            self.select_user(remaining[0]["id"])


class PlaylistService:
    """User-scoped playlist workflows."""

    def __init__(
        self,
        playlists: PlaylistRepositoryProtocol,
        state: AppState,
    ) -> None:
        self._playlists = playlists
        self._state = state

    def list_playlists(self, user_id: int) -> list[Playlist]:
        return self._playlists.list_for_user(user_id)

    def create_playlist(self, user_id: int, name: str) -> Playlist:
        cleaned = name.strip()
        if not cleaned:
            logger.warning("playlist create rejected empty name")
            raise ValidationError("Playlist name must not be empty")
        playlist = self._playlists.create(user_id, cleaned)
        logger.info(
            "playlist created id=%s name=%s user_id=%s",
            playlist["id"],
            playlist["name"],
            user_id,
        )
        return playlist

    def get_playlist(self, playlist_id: int) -> Playlist:
        playlist = self._playlists.get(playlist_id)
        if playlist is None:
            logger.warning("playlist missing id=%s", playlist_id)
            raise ValidationError("Playlist not found")
        return playlist

    def adopt_working_playlist(self, playlist: Playlist) -> None:
        self._state.current_playlist.set(playlist)

    def create_playlist_from_songs(
        self,
        user_id: int,
        name: str,
        songs: list[Song],
    ) -> Playlist:
        if not songs:
            logger.warning("playlist create from songs rejected empty list")
            raise ValidationError("Playlist songs must not be empty")
        playlist = self.create_playlist(user_id, name)
        return self.replace_songs(playlist["id"], songs)

    def replace_songs(self, playlist_id: int, songs: list[Song]) -> Playlist:
        logger.info("playlist replace id=%s count=%s", playlist_id, len(songs))
        playlist = self._playlists.replace_songs(playlist_id, songs)
        current = self._state.current_playlist.get()
        if current is not None and current["id"] == playlist_id:
            self._state.current_playlist.set(playlist)
        return playlist

    def add_song(self, playlist_id: int, song: Song) -> None:
        logger.info(
            "playlist add id=%s video_id=%s",
            playlist_id,
            song["video_id"],
        )
        self._playlists.add_song(playlist_id, song)
        self._refresh_working_playlist(playlist_id)

    def remove_song(self, playlist_id: int, video_id: str) -> None:
        logger.info("playlist remove id=%s video_id=%s", playlist_id, video_id)
        self._playlists.remove_song(playlist_id, video_id)
        self._refresh_working_playlist(playlist_id)

    def delete_playlist(self, playlist_id: int) -> None:
        logger.info("playlist deleted id=%s", playlist_id)
        self._playlists.delete(playlist_id)
        current = self._state.current_playlist.get()
        if current is not None and current["id"] == playlist_id:
            self._state.current_playlist.set(None)

    def _refresh_working_playlist(self, playlist_id: int) -> None:
        current = self._state.current_playlist.get()
        if current is not None and current["id"] == playlist_id:
            refreshed = self.get_playlist(playlist_id)
            if self._state.current_playlist.get() is current:
                self._state.current_playlist.set(refreshed)


class SettingsService:
    """Per-user default volume and search result limit."""

    def __init__(
        self,
        users: UserRepositoryProtocol,
        state: AppState,
    ) -> None:
        self._users = users
        self._state = state

    def get(self) -> UserSettings:
        user = self._state.current_user.get()
        if user is None:
            return {
                "default_volume": DEFAULT_VOLUME,
                "search_limit": DEFAULT_SEARCH_LIMIT,
            }
        return {
            "default_volume": user["default_volume"],
            "search_limit": user["search_limit"],
        }

    def save(self, settings: UserSettings) -> UserSettings:
        volume = settings["default_volume"]
        limit = settings["search_limit"]
        if volume < 0 or volume > MAX_VOLUME:
            logger.warning("settings save rejected volume=%s", volume)
            raise ValidationError(f"Volume must be between 0 and {MAX_VOLUME}")
        if limit < MIN_SEARCH_LIMIT or limit > MAX_SEARCH_LIMIT:
            logger.warning("settings save rejected search_limit=%s", limit)
            raise ValidationError(
                f"Search limit must be between {MIN_SEARCH_LIMIT} "
                f"and {MAX_SEARCH_LIMIT}"
            )
        user = self._state.current_user.get()
        if user is None:
            logger.warning("settings save rejected no profile")
            raise ValidationError("No profile selected")
        updated = self._users.update_settings(
            user["id"],
            {"default_volume": volume, "search_limit": limit},
        )
        current = self._state.current_user.get()
        if current is not None and current["id"] == updated["id"]:
            self._state.current_user.set(updated)
        logger.info(
            "settings saved volume=%s search_limit=%s",
            updated["default_volume"],
            updated["search_limit"],
        )
        return {
            "default_volume": updated["default_volume"],
            "search_limit": updated["search_limit"],
        }
