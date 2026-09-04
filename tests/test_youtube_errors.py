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


def test_get_stream_returns_url_and_headers_from_top_level_info(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = {
        "url": "https://googlevideo.com/videoplayback?id=123",
        "http_headers": {
            "User-Agent": "test-agent",
            "Referer": "https://www.youtube.com/",
        },
    }
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    stream = youtube_no_init.get_stream("dQw4w9WgXcQ")
    assert stream["url"] == "https://googlevideo.com/videoplayback?id=123"
    assert stream["http_headers"] == {
        "User-Agent": "test-agent",
        "Referer": "https://www.youtube.com/",
    }


def test_get_stream_returns_url_and_headers_from_best_audio_format(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = {
        "http_headers": {"User-Agent": "default-agent"},
        "formats": [
            {
                "acodec": "opus",
                "url": "https://googlevideo.com/videoplayback?fmt=opus",
                "http_headers": {
                    "User-Agent": "format-agent",
                    "Referer": "https://www.youtube.com/",
                },
            }
        ],
    }
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    stream = youtube_no_init.get_stream("dQw4w9WgXcQ")
    assert stream["url"] == "https://googlevideo.com/videoplayback?fmt=opus"
    assert stream["http_headers"] == {
        "User-Agent": "format-agent",
        "Referer": "https://www.youtube.com/",
    }


def test_get_stream_raises_track_not_found_when_info_missing(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = None
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(TrackNotFoundError, match="Could not extract info"):
        youtube_no_init.get_stream("dQw4w9WgXcQ")


def test_get_stream_raises_track_not_found_when_no_audio_format(
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
        youtube_no_init.get_stream("dQw4w9WgXcQ")


def test_get_stream_wraps_ydl_failure_as_stream_extraction_error(
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
        youtube_no_init.get_stream("dQw4w9WgXcQ")
    assert isinstance(exc_info.value.__cause__, OSError)


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
    assert song["video_id"] == "abc12345678"
    assert song["title"] == "Test Track"
    assert song["artist"] == "Test Artist"
    assert song["album"] == "Test Album"
    assert song["duration"] == 180


def test_convert_entry_to_song_returns_none_without_id(
    youtube_no_init: Youtube,
) -> None:
    assert youtube_no_init._convert_entry_to_song({"title": "No ID"}) is None


def test_convert_entry_to_song_treats_none_duration_as_zero(
    youtube_no_init: Youtube,
) -> None:
    entry: dict[str, Any] = {
        "id": "livestream01",
        "title": "Lofi Radio",
        "uploader": "Chill",
        "duration": None,
    }
    song = youtube_no_init._convert_entry_to_song(entry)
    assert song is not None
    assert song["duration"] == 0


def test_search_uses_extract_flat_in_playlist(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = {"entries": []}
    patched = mocker.patch(
        "ytmusic_cli.music.youtube.YoutubeDL",
        return_value=mock_ydl,
    )

    youtube_no_init.search("lofi")

    called_opts = patched.call_args[0][0]
    assert called_opts["extract_flat"] == "in_playlist"
