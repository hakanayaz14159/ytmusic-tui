"""Tests for the domain exception hierarchy."""

from ytmusic_cli.exceptions import (
    DatabaseError,
    PlaybackError,
    StreamExtractionError,
    TrackNotFoundError,
    ValidationError,
    YTMusicError,
)


def test_all_domain_errors_are_subclasses_of_ytmusic_error() -> None:
    assert issubclass(PlaybackError, YTMusicError)
    assert issubclass(StreamExtractionError, YTMusicError)
    assert issubclass(TrackNotFoundError, YTMusicError)
    assert issubclass(DatabaseError, YTMusicError)
    assert issubclass(ValidationError, YTMusicError)


def test_ytmusic_error_is_exception_subclass() -> None:
    assert issubclass(YTMusicError, Exception)


def test_exception_message_passthrough() -> None:
    playback_error = PlaybackError("VLC failed to initialize")
    assert str(playback_error) == "VLC failed to initialize"

    stream_error = StreamExtractionError("no stream found")
    assert str(stream_error) == "no stream found"


def test_exception_chaining_preserves_cause() -> None:
    original = ValueError("underlying failure")
    try:
        raise PlaybackError("playback failed") from original
    except PlaybackError as err:
        assert err.__cause__ is original
        assert str(err) == "playback failed"


def test_stream_extraction_error_chaining() -> None:
    cause = RuntimeError("yt-dlp blew up")
    try:
        raise StreamExtractionError("search failed") from cause
    except StreamExtractionError as err:
        assert isinstance(err, YTMusicError)
        assert err.__cause__ is cause
