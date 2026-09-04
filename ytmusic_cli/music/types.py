from enum import StrEnum
from typing import NamedTuple, TypedDict


class Song(TypedDict):
    video_id: str
    title: str
    artist: str | None
    album: str | None
    duration: int


class AudioStream(TypedDict):
    url: str
    http_headers: dict[str, str]


class Playlist(TypedDict):
    id: int
    name: str
    songs: list[Song]


class UserSettings(TypedDict):
    default_volume: int
    search_limit: int


class User(TypedDict):
    id: int
    username: str
    default_volume: int
    search_limit: int


class PlaybackStatus(StrEnum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class PlaybackState(TypedDict):
    status: PlaybackStatus
    volume: int
    position: float
    duration: int


class PlaybackTickAction(StrEnum):
    IDLE = "idle"
    ENDED = "ended"
    FAILED = "failed"


class PlaybackTick(NamedTuple):
    action: PlaybackTickAction
    message: str | None = None
