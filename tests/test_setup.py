"""Initial verification and TDD baseline tests."""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from peewee import SqliteDatabase

from ytmusic_cli import __version__
from ytmusic_cli.db.playlist import Playlist
from ytmusic_cli.db.song import Song
from ytmusic_cli.db.user import User
from ytmusic_cli.main import YTMusicApp, main


def test_cli_version() -> None:
    """Verify CLI --version outputs the correct version."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help() -> None:
    """Verify CLI --help displays usage information."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "YTMusic CLI" in result.output


@pytest.mark.asyncio
async def test_tui_app_lifecycle() -> None:
    """Verify the Textual app mounts correctly and responds to quit binding."""
    app = YTMusicApp()
    async with app.run_test() as pilot:
        assert app.is_running
        await pilot.press("q")
    assert not app.is_running


def test_database_in_memory_isolation(test_db: SqliteDatabase) -> None:
    """Verify models can be created and queried in the in-memory test database."""
    user = User.create(username="audiophile")
    song = Song.create(
        title="Lofi Beat 1",
        artist="Chill Producer",
        duration=180,
        url="https://www.youtube.com/watch?v=sample1",
    )
    playlist = Playlist.create(name="Study Vibes", user=user)
    playlist.songs.add(song)

    assert user.playlists.count() == 1
    assert playlist.songs.count() == 1
    retrieved_user = User.get(User.username == "audiophile")
    assert retrieved_user.username == "audiophile"


def test_mock_youtube_fixture(mock_youtube: MagicMock) -> None:
    """Verify mock_youtube fixture returns sample songs and a stream."""
    results = mock_youtube.search("lofi", max_results=2)
    assert len(results) == 2
    assert results[0]["title"] == "Sample Song 1"
    assert results[0]["video_id"] == "sample1"

    stream = mock_youtube.get_stream("sample1")
    assert stream["url"].startswith("https://")


def test_mock_player_fixture(mock_player: MagicMock) -> None:
    """Verify mock_player fixture tracks playback state."""
    assert mock_player.is_playing() is False
    mock_player.play("https://stream.example.com/audio.m4a")
    assert mock_player.is_playing() is True
    assert mock_player.state["current_url"] == "https://stream.example.com/audio.m4a"

    mock_player.pause()
    assert mock_player.is_playing() is False

    mock_player.set_volume(50)
    assert mock_player.get_volume() == 50
