"""Reactive application state singleton."""

from collections.abc import Callable
from typing import Generic, TypeVar

from ytmusic_tui.consts import DEFAULT_VOLUME
from ytmusic_tui.music.types import (
    PlaybackState,
    PlaybackStatus,
    Playlist,
    Song,
    User,
)
from ytmusic_tui.utils import singleton

T = TypeVar("T")


def _default_playback_state() -> PlaybackState:
    return {
        "status": PlaybackStatus.STOPPED,
        "volume": DEFAULT_VOLUME,
        "position": 0.0,
        "duration": 0,
    }


class AtomicData(Generic[T]):
    def __init__(self, data: T) -> None:
        self._data = data
        self._subscribers: list[Callable[[T], None]] = []

    def get(self) -> T:
        return self._data

    def set(self, data: T) -> None:
        self._data = data
        self._notify_subscribers()

    def __str__(self) -> str:
        return str(self._data)

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        """Subscribe to data changes. Returns an unsubscribe function."""
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            """Unsubscribe this specific callback."""
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe

    def _notify_subscribers(self) -> None:
        """Notify all subscribers of data changes."""
        for callback in self._subscribers:
            callback(self._data)


@singleton
class AppState:
    """Application state."""

    def __init__(self) -> None:
        self.current_song: AtomicData[Song | None] = AtomicData(None)
        self.current_user: AtomicData[User | None] = AtomicData(None)
        self.current_playlist: AtomicData[Playlist | None] = AtomicData(None)
        self.playback_state: AtomicData[PlaybackState] = AtomicData(
            _default_playback_state()
        )
        self.queue: AtomicData[list[Song]] = AtomicData([])
        self.queue_index: AtomicData[int] = AtomicData(-1)

    def reset(self) -> None:
        """Reset all state to initial values."""
        self.current_song.set(None)
        self.current_user.set(None)
        self.current_playlist.set(None)
        self.playback_state.set(_default_playback_state())
        self.queue.set([])
        self.queue_index.set(-1)
