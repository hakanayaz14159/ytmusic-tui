"""Application services for search, playback, accounts, playlists, and settings."""

from ytmusic_cli.consts import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_USERNAME,
    DEFAULT_VOLUME,
    MAX_SEARCH_LIMIT,
    MAX_VOLUME,
    MIN_SEARCH_LIMIT,
)
from ytmusic_cli.exceptions import ValidationError
from ytmusic_cli.music.ports import (
    AudioPlayerProtocol,
    MusicSourceProtocol,
    PlaylistRepositoryProtocol,
    UserRepositoryProtocol,
)
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import (
    PlaybackState,
    PlaybackStatus,
    Playlist,
    Song,
    User,
    UserSettings,
)

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
    """Orchestrates stream resolution, player control, queue, and AppState."""

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
        self._align_queue_for_play(song)
        self._start_playback(song)

    def append_to_queue(self, song: Song) -> None:
        queue = [*self._state.queue.get(), song]
        self._state.queue.set(queue)
        status = self._state.playback_state.get()["status"]
        if status == PlaybackStatus.STOPPED:
            self.play_song(song)

    def play_queue(self, songs: list[Song], start_index: int = 0) -> None:
        if not songs:
            raise ValidationError("Playlist is empty")
        index = max(0, min(start_index, len(songs) - 1))
        self._state.queue.set(list(songs))
        self._state.queue_index.set(index)
        self._start_playback(songs[index])

    def play_next(self) -> None:
        queue = self._state.queue.get()
        next_index = self._state.queue_index.get() + 1
        if 0 <= next_index < len(queue):
            self._state.queue_index.set(next_index)
            self._start_playback(queue[next_index])
            return
        if self._state.playback_state.get()["status"] == PlaybackStatus.PLAYING:
            self._patch_playback(status=PlaybackStatus.STOPPED)

    def play_previous(self) -> None:
        queue = self._state.queue.get()
        prev_index = self._state.queue_index.get() - 1
        if prev_index >= 0 and queue:
            self._state.queue_index.set(prev_index)
            self._start_playback(queue[prev_index])

    def remove_from_queue(self, index: int) -> None:
        queue = list(self._state.queue.get())
        if index < 0 or index >= len(queue):
            raise ValidationError("Queue index out of range")
        current = self._state.queue_index.get()
        del queue[index]
        self._state.queue.set(queue)
        if not queue:
            self._state.queue_index.set(-1)
            return
        if index < current:
            self._state.queue_index.set(current - 1)
        elif index == current:
            new_index = min(index, len(queue) - 1)
            self._state.queue_index.set(new_index)
            if self._state.playback_state.get()["status"] == PlaybackStatus.PLAYING:
                self._start_playback(queue[new_index])

    def toggle(self) -> None:
        current = self._state.playback_state.get()
        status = current["status"]
        if status == PlaybackStatus.PLAYING:
            self._player.pause()
            self._set_status(PlaybackStatus.PAUSED)
        elif status == PlaybackStatus.PAUSED:
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
            self.play_next()
            return
        position = self._player.get_position()
        if int(position) == int(current["position"]):
            return
        self._patch_playback(position=position)

    def _align_queue_for_play(self, song: Song) -> None:
        queue = list(self._state.queue.get())
        if not queue:
            self._state.queue.set([song])
            self._state.queue_index.set(0)
            return
        for index, item in enumerate(queue):
            if item["video_id"] == song["video_id"]:
                self._state.queue_index.set(index)
                return

    def _start_playback(self, song: Song) -> None:
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
            raise ValidationError("Profile name must not be empty")
        return self._users.create_user(cleaned)

    def select_user(self, user_id: int) -> User:
        user = self._users.get_user(user_id)
        if user is None:
            raise ValidationError("Profile not found")
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
            raise ValidationError("Cannot delete the last profile")
        self._users.delete_user(user_id)
        current = self._state.current_user.get()
        if current is not None and current["id"] == user_id:
            remaining = self._users.list_users()
            self.select_user(remaining[0]["id"])


class PlaylistService:
    """User-scoped playlist workflows."""

    def __init__(self, playlists: PlaylistRepositoryProtocol) -> None:
        self._playlists = playlists

    def list_playlists(self, user_id: int) -> list[Playlist]:
        return self._playlists.list_for_user(user_id)

    def create_playlist(self, user_id: int, name: str) -> Playlist:
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Playlist name must not be empty")
        return self._playlists.create(user_id, cleaned)

    def get_playlist(self, playlist_id: int) -> Playlist:
        playlist = self._playlists.get(playlist_id)
        if playlist is None:
            raise ValidationError("Playlist not found")
        return playlist

    def add_song(self, playlist_id: int, song: Song) -> None:
        self._playlists.add_song(playlist_id, song)

    def remove_song(self, playlist_id: int, video_id: str) -> None:
        self._playlists.remove_song(playlist_id, video_id)

    def delete_playlist(self, playlist_id: int) -> None:
        self._playlists.delete(playlist_id)


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
            raise ValidationError(f"Volume must be between 0 and {MAX_VOLUME}")
        if limit < MIN_SEARCH_LIMIT or limit > MAX_SEARCH_LIMIT:
            raise ValidationError(
                f"Search limit must be between {MIN_SEARCH_LIMIT} "
                f"and {MAX_SEARCH_LIMIT}"
            )
        user = self._state.current_user.get()
        if user is None:
            raise ValidationError("No profile selected")
        updated = self._users.update_settings(
            user["id"],
            {"default_volume": volume, "search_limit": limit},
        )
        self._state.current_user.set(updated)
        return {
            "default_volume": updated["default_volume"],
            "search_limit": updated["search_limit"],
        }
