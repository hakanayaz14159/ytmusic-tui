"""Peewee adapters that map persistence rows to domain types."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from peewee import DatabaseError as PeeweeDatabaseError
from peewee import IntegrityError

from ytmusic_tui.db.playlist import Playlist as DbPlaylist
from ytmusic_tui.db.song import Song as DbSong
from ytmusic_tui.db.user import User as DbUser
from ytmusic_tui.exceptions import DatabaseError, ValidationError
from ytmusic_tui.music.ports import SongRepositoryProtocol
from ytmusic_tui.music.types import Playlist, Song, User, UserSettings

P = ParamSpec("P")
T = TypeVar("T")


def _database_operation(operation: Callable[P, T]) -> Callable[P, T]:
    @wraps(operation)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return operation(*args, **kwargs)
        except PeeweeDatabaseError as err:
            raise DatabaseError(f"Database operation failed: {err}") from err

    return wrapped


def _to_user(row: DbUser) -> User:
    return {
        "id": int(row.id),
        "username": str(row.username),
        "default_volume": int(row.default_volume),
        "search_limit": int(row.search_limit),
    }


def _to_song(row: DbSong) -> Song:
    return {
        "video_id": str(row.video_id),
        "title": str(row.title),
        "artist": str(row.artist) if row.artist else None,
        "album": str(row.album) if row.album else None,
        "duration": int(row.duration or 0),
    }


def _playlist_songs(row: DbPlaylist) -> list[Song]:
    through = DbPlaylist.songs.get_through_model()
    query = (
        DbSong.select()
        .join(through)
        .where(through.playlist == row)
        .order_by(through.id)
    )
    return [_to_song(song) for song in query]


def _to_playlist(row: DbPlaylist) -> Playlist:
    return {
        "id": int(row.id),
        "name": str(row.name),
        "songs": _playlist_songs(row),
    }


class UserRepository:
    @_database_operation
    def list_users(self) -> list[User]:
        return [_to_user(row) for row in DbUser.select().order_by(DbUser.username)]

    @_database_operation
    def create_user(self, username: str) -> User:
        try:
            row = DbUser.create(username=username)
        except IntegrityError as err:
            raise DatabaseError(f"Username already exists: {username}") from err
        return _to_user(row)

    @_database_operation
    def get_user(self, user_id: int) -> User | None:
        row = DbUser.get_or_none(DbUser.id == user_id)
        return _to_user(row) if row is not None else None

    @_database_operation
    def get_by_username(self, username: str) -> User | None:
        row = DbUser.get_or_none(DbUser.username == username)
        return _to_user(row) if row is not None else None

    @_database_operation
    def delete_user(self, user_id: int) -> None:
        with DbUser._meta.database.atomic():
            row = DbUser.get_or_none(DbUser.id == user_id)
            if row is None:
                raise DatabaseError(f"User {user_id} not found")
            row.delete_instance(recursive=True)

    @_database_operation
    def update_settings(self, user_id: int, settings: UserSettings) -> User:
        row = DbUser.get_or_none(DbUser.id == user_id)
        if row is None:
            raise DatabaseError(f"User {user_id} not found")
        row.default_volume = settings["default_volume"]
        row.search_limit = settings["search_limit"]
        row.save()
        return _to_user(row)


class SongRepository:
    @_database_operation
    def upsert(self, song: Song) -> Song:
        row = DbSong.get_or_none(DbSong.video_id == song["video_id"])
        if row is None:
            row = DbSong.create(
                video_id=song["video_id"],
                title=song["title"],
                artist=song["artist"],
                album=song["album"],
                duration=song["duration"],
            )
            return _to_song(row)
        row.title = song["title"]
        row.artist = song["artist"]
        row.album = song["album"]
        row.duration = song["duration"]
        row.save()
        return _to_song(row)

    @_database_operation
    def get_by_video_id(self, video_id: str) -> Song | None:
        row = DbSong.get_or_none(DbSong.video_id == video_id)
        return _to_song(row) if row is not None else None


class PlaylistRepository:
    def __init__(self, songs: SongRepositoryProtocol) -> None:
        self._songs = songs

    @_database_operation
    def list_for_user(self, user_id: int) -> list[Playlist]:
        query = (
            DbPlaylist.select()
            .where(DbPlaylist.user == user_id)
            .order_by(DbPlaylist.name)
        )
        return [_to_playlist(row) for row in query]

    @_database_operation
    def create(self, user_id: int, name: str) -> Playlist:
        user = DbUser.get_or_none(DbUser.id == user_id)
        if user is None:
            raise DatabaseError(f"User {user_id} not found")
        row = DbPlaylist.create(name=name, user=user)
        return _to_playlist(row)

    @_database_operation
    def get(self, playlist_id: int) -> Playlist | None:
        row = DbPlaylist.get_or_none(DbPlaylist.id == playlist_id)
        return _to_playlist(row) if row is not None else None

    @_database_operation
    def add_song(self, playlist_id: int, song: Song) -> None:
        with DbPlaylist._meta.database.atomic():
            playlist = DbPlaylist.get_or_none(DbPlaylist.id == playlist_id)
            if playlist is None:
                raise DatabaseError(f"Playlist {playlist_id} not found")
            if playlist.songs.where(DbSong.video_id == song["video_id"]).exists():
                raise ValidationError("Song is already in this playlist")
            db_song = self._songs.upsert(song)
            row = DbSong.get(DbSong.video_id == db_song["video_id"])
            playlist.songs.add(row)

    @_database_operation
    def remove_song(self, playlist_id: int, video_id: str) -> None:
        playlist = DbPlaylist.get_or_none(DbPlaylist.id == playlist_id)
        if playlist is None:
            raise DatabaseError(f"Playlist {playlist_id} not found")
        row = DbSong.get_or_none(DbSong.video_id == video_id)
        if row is None:
            raise DatabaseError(f"Song {video_id} not found")
        playlist.songs.remove(row)

    @_database_operation
    def replace_songs(self, playlist_id: int, songs: list[Song]) -> Playlist:
        with DbPlaylist._meta.database.atomic():
            playlist = DbPlaylist.get_or_none(DbPlaylist.id == playlist_id)
            if playlist is None:
                raise DatabaseError(f"Playlist {playlist_id} not found")
            playlist.songs.clear()
            seen: set[str] = set()
            for song in songs:
                video_id = song["video_id"]
                if video_id in seen:
                    continue
                seen.add(video_id)
                self._songs.upsert(song)
                row = DbSong.get(DbSong.video_id == video_id)
                playlist.songs.add(row)
            return _to_playlist(playlist)

    @_database_operation
    def delete(self, playlist_id: int) -> None:
        with DbPlaylist._meta.database.atomic():
            row = DbPlaylist.get_or_none(DbPlaylist.id == playlist_id)
            if row is None:
                raise DatabaseError(f"Playlist {playlist_id} not found")
            row.delete_instance(recursive=True)
