from enum import StrEnum
from typing import TypedDict


class Song(TypedDict):
    id: int
    title: str
    artist: str | None
    album: str | None
    duration: int
    url: str


class AudioStream(TypedDict):
    url: str
    http_headers: dict[str, str]


class Playlist(TypedDict):
    id: int
    name: str
    songs: list[Song]


class User(TypedDict):
    id: int
    username: str
    playlists: list[Playlist]


class PlaybackStatus(StrEnum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class PlaybackState(TypedDict):
    status: PlaybackStatus
    volume: int
    position: float
    duration: int
