from collections.abc import Callable
from typing import TYPE_CHECKING, Generic, TypeVar

from ytmusic_cli.utils import singleton

if TYPE_CHECKING:
    from ytmusic_cli.music.types import Playlist, Song, User

T = TypeVar("T")


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

    def unsubscribe(self, callback: Callable[[T], None]) -> None:
        """Unsubscribe from data changes."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

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

    def reset(self) -> None:
        """Reset all state to initial values."""
        self.current_song.set(None)
        self.current_user.set(None)
        self.current_playlist.set(None)
