"""Playlist use cases scoped to the active profile."""

import logging

from ytmusic_tui.exceptions import ValidationError
from ytmusic_tui.music.ports import PlaylistRepositoryProtocol
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import Playlist, Song

logger = logging.getLogger(__name__)


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
