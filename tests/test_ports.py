"""Tests for AudioPlayerProtocol and MusicSourceProtocol ports."""

from unittest.mock import MagicMock

from ytmusic_cli.music.ports import AudioPlayerProtocol, MusicSourceProtocol
from ytmusic_cli.music.types import AudioStream


def test_mock_player_satisfies_audio_player_protocol(
    mock_player: MagicMock,
) -> None:
    assert isinstance(mock_player, AudioPlayerProtocol)


def test_mock_youtube_satisfies_music_source_protocol(
    mock_youtube: MagicMock,
) -> None:
    assert isinstance(mock_youtube, MusicSourceProtocol)


def test_incomplete_player_fails_audio_player_protocol() -> None:
    class IncompletePlayer:
        def play(self, stream: AudioStream) -> None:
            pass

    assert not isinstance(IncompletePlayer(), AudioPlayerProtocol)


def test_incomplete_source_fails_music_source_protocol() -> None:
    class IncompleteSource:
        def search(self, query: str, max_results: int = 10) -> list[object]:
            return []

    assert not isinstance(IncompleteSource(), MusicSourceProtocol)


def test_complete_dummy_player_satisfies_protocol() -> None:
    class DummyPlayer:
        def play(self, stream: AudioStream) -> None:
            pass

        def pause(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def is_playing(self) -> bool:
            return False

        def set_volume(self, volume: int) -> None:
            pass

        def get_volume(self) -> int:
            return 80

        def get_position(self) -> float:
            return 0.0

        def has_ended(self) -> bool:
            return False

        def has_failed(self) -> bool:
            return False

        def engine_state(self) -> str:
            return "Stopped"

    assert isinstance(DummyPlayer(), AudioPlayerProtocol)


def test_complete_dummy_source_satisfies_protocol() -> None:
    class DummySource:
        def search(self, query: str, max_results: int = 10) -> list[object]:
            return []

        def get_stream(self, video_id: str) -> AudioStream:
            return {"url": "https://stream.example.com/audio.m4a", "http_headers": {}}

    assert isinstance(DummySource(), MusicSourceProtocol)
