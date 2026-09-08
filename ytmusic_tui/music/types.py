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


class SkipKeymap(StrEnum):
    ISO = "iso"
    ANSI = "ansi"


class SkipKeymapMode(StrEnum):
    AUTO = "auto"
    ISO = "iso"
    ANSI = "ansi"


class StartupSettings(TypedDict):
    skip_welcome: bool
    default_user_id: int | None
    skip_keymap: SkipKeymapMode


def default_startup_settings() -> StartupSettings:
    return {
        "skip_welcome": False,
        "default_user_id": None,
        "skip_keymap": SkipKeymapMode.AUTO,
    }


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
