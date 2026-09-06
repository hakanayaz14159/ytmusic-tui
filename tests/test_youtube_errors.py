"""Tests for domain exception hygiene in the YouTube adapter."""

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
    entry: dict[str, object] = {
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


def test_convert_entry_to_song_rejects_non_mapping(
    youtube_no_init: Youtube,
) -> None:
    assert youtube_no_init._convert_entry_to_song("not-an-entry") is None


def test_get_stream_rejects_non_string_headers(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = {
        "url": "https://googlevideo.com/videoplayback?id=123",
        "http_headers": {"User-Agent": 1},
    }
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(StreamExtractionError, match="Invalid stream headers"):
        youtube_no_init.get_stream("dQw4w9WgXcQ")


def test_convert_entry_to_song_defaults_missing_uploader_to_unknown_uploader(
    youtube_no_init: Youtube,
) -> None:
    entry: dict[str, object] = {
        "id": "noidcredit1",
        "title": "No Credit",
        "duration": 90,
    }
    song = youtube_no_init._convert_entry_to_song(entry)
    assert song is not None
    assert song["artist"] == "Unknown Uploader"


def test_convert_entry_to_song_treats_none_duration_as_zero(
    youtube_no_init: Youtube,
) -> None:
    entry: dict[str, object] = {
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


def test_get_stream_pins_android_player_client(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = {
        "url": "https://googlevideo.com/videoplayback?itag=18",
        "http_headers": {"User-Agent": "test-agent"},
    }
    patched = mocker.patch(
        "ytmusic_cli.music.youtube.YoutubeDL",
        return_value=mock_ydl,
    )

    youtube_no_init.get_stream("dQw4w9WgXcQ")

    called_opts = patched.call_args[0][0]
    extractor_args = called_opts["extractor_args"]
    assert isinstance(extractor_args, dict)
    youtube_args = extractor_args["youtube"]
    assert isinstance(youtube_args, dict)
    assert youtube_args["player_client"] == ["android"]


def test_get_stream_prefers_best_audio_only_format_and_merges_headers(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "http_headers": {
            "User-Agent": "default-agent",
            "Referer": "https://www.youtube.com/",
        },
        "formats": [
            {"acodec": "opus", "vcodec": "none", "url": "https://audio/low"},
            {
                "acodec": "opus",
                "vcodec": "none",
                "url": "https://audio/high",
                "http_headers": {"User-Agent": "format-agent"},
            },
            {"acodec": "aac", "vcodec": "avc1", "url": "https://video/high"},
        ],
    }
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    stream = youtube_no_init.get_stream("dQw4w9WgXcQ")

    assert stream == {
        "url": "https://audio/high",
        "http_headers": {
            "User-Agent": "format-agent",
            "Referer": "https://www.youtube.com/",
        },
    }


def test_get_stream_skips_formats_without_an_audio_codec(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "formats": [
            {"url": "https://storyboard/image"},
            {"acodec": "none", "url": "https://video/silent"},
        ]
    }
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL", return_value=mock_ydl)

    with pytest.raises(TrackNotFoundError, match="No audio stream"):
        youtube_no_init.get_stream("dQw4w9WgXcQ")


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), "inf", "NaN"])
def test_convert_entry_to_song_defaults_nonfinite_duration_to_zero(
    youtube_no_init: Youtube,
    duration: object,
) -> None:
    song = youtube_no_init._convert_entry_to_song(
        {"id": "live", "title": "Live Radio", "duration": duration}
    )

    assert song is not None
    assert song["duration"] == 0


def test_convert_entry_to_song_falls_back_to_channel_for_null_uploader(
    youtube_no_init: Youtube,
) -> None:
    song = youtube_no_init._convert_entry_to_song(
        {"id": "track", "uploader": None, "channel": "Channel name"}
    )

    assert song is not None
    assert song["artist"] == "Channel name"
