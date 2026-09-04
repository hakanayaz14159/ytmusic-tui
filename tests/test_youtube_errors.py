"""Tests for domain exception hygiene in the YouTube adapter."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from ytmusic_cli.exceptions import StreamExtractionError, TrackNotFoundError
from ytmusic_cli.music.youtube import Youtube


@pytest.fixture
def youtube_no_init(mocker: MockerFixture) -> Youtube:
    """Construct Youtube without calling real YoutubeDL.__init__."""
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL")
    return Youtube()


def test_search_raises_stream_extraction_error_on_ydl_failure(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.side_effect = RuntimeError("network down")
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(StreamExtractionError, match="Search failed") as exc_info:
        youtube_no_init.search("lofi")
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_get_stream_url_raises_track_not_found_when_info_missing(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = None
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(TrackNotFoundError, match="Could not extract info"):
        youtube_no_init.get_stream_url("dQw4w9WgXcQ")


def test_get_stream_url_raises_track_not_found_when_no_audio_format(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = {
        "formats": [{"acodec": "none", "url": "https://example.com/video"}],
    }
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(TrackNotFoundError, match="No audio stream URL found"):
        youtube_no_init.get_stream_url("dQw4w9WgXcQ")


def test_get_stream_url_wraps_ydl_failure_as_stream_extraction_error(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.side_effect = OSError("tls error")
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(
        StreamExtractionError, match="Failed to get stream URL"
    ) as exc_info:
        youtube_no_init.get_stream_url("dQw4w9WgXcQ")
    assert isinstance(exc_info.value.__cause__, OSError)


def test_get_metadata_raises_track_not_found_when_info_missing(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = None
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(TrackNotFoundError, match="Could not extract info"):
        youtube_no_init.get_metadata("dQw4w9WgXcQ")


def test_normalize_video_url_with_video_id(youtube_no_init: Youtube) -> None:
    assert (
        youtube_no_init._normalize_video_url("dQw4w9WgXcQ")
        == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )


def test_normalize_video_url_passthrough_full_url(youtube_no_init: Youtube) -> None:
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert youtube_no_init._normalize_video_url(url) == url


def test_normalize_video_url_extracts_from_embed_path(
    youtube_no_init: Youtube,
) -> None:
    assert (
        youtube_no_init._normalize_video_url("/embed/dQw4w9WgXcQ")
        == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )


def test_convert_entry_to_song(youtube_no_init: Youtube) -> None:
    entry: dict[str, Any] = {
        "id": "abc12345678",
        "title": "Test Track",
        "uploader": "Test Artist",
        "album": "Test Album",
        "duration": 180,
    }
    song = youtube_no_init._convert_entry_to_song(entry)
    assert song is not None
    assert song["title"] == "Test Track"
    assert song["artist"] == "Test Artist"
    assert song["album"] == "Test Album"
    assert song["duration"] == 180
    assert song["url"] == "https://www.youtube.com/watch?v=abc12345678"


def test_convert_entry_to_song_returns_none_without_id(
    youtube_no_init: Youtube,
) -> None:
    assert youtube_no_init._convert_entry_to_song({"title": "No ID"}) is None
