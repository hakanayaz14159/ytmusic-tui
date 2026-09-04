"""Tests for the autouse AppState reset fixture."""

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackStatus


def test_app_state_is_clean_at_test_start() -> None:
    state = AppState()
    assert state.current_song.get() is None
    assert state.current_user.get() is None
    assert state.current_playlist.get() is None
    playback = state.playback_state.get()
    assert playback["status"] == PlaybackStatus.STOPPED
    assert playback["volume"] == 80


def test_app_state_mutations_do_not_leak_to_next_test_part_a() -> None:
    state = AppState()
    state.current_song.set(
        {
            "id": 1,
            "title": "Leak Check",
            "artist": None,
            "album": None,
            "duration": 1,
            "url": "https://www.youtube.com/watch?v=leak",
        }
    )
    state.playback_state.set(
        {
            "status": PlaybackStatus.PLAYING,
            "volume": 10,
            "position": 5.0,
            "duration": 1,
        }
    )


def test_app_state_mutations_do_not_leak_to_next_test_part_b() -> None:
    state = AppState()
    assert state.current_song.get() is None
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert state.playback_state.get()["volume"] == 80
