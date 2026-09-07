"""Guards that the shared test doubles still satisfy the domain ports."""

from unittest.mock import MagicMock

from ytmusic_cli.music.ports import AudioPlayerProtocol, MusicSourceProtocol


def test_mock_player_satisfies_audio_player_protocol(
    mock_player: MagicMock,
) -> None:
    assert isinstance(mock_player, AudioPlayerProtocol)


def test_mock_youtube_satisfies_music_source_protocol(
    mock_youtube: MagicMock,
) -> None:
    assert isinstance(mock_youtube, MusicSourceProtocol)
