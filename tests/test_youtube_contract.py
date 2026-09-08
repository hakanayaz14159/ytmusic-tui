"""Live YouTube contract tests for the yt-dlp adapter."""

from urllib.request import Request, urlopen

import pytest
from pytest_mock import MockerFixture

from ytmusic_tui.music.ports import MusicSourceProtocol
from ytmusic_tui.music.youtube import Youtube

_ME_AT_THE_ZOO = "jNQXAC9IVRw"


@pytest.mark.network
def test_get_stream_serves_audio_bytes_with_returned_headers(
    requires_network: None,
) -> None:
    stream = Youtube().get_stream(_ME_AT_THE_ZOO)
    request = Request(stream["url"], method="GET")
    request.add_header("Range", "bytes=0-1023")
    for name, value in stream["http_headers"].items():
        request.add_header(name, value)

    with urlopen(request, timeout=15) as response:
        assert response.status == 206
        content_type = response.headers.get_content_type()
        assert content_type.startswith(("audio/", "video/"))


@pytest.mark.network
def test_suggest_returns_query_strings(
    requires_network: None,
) -> None:
    suggestions = Youtube().suggest("beatles", max_results=5)
    assert 1 <= len(suggestions) <= 5
    for suggestion in suggestions:
        assert suggestion.strip()


@pytest.mark.network
def test_search_returns_requested_number_of_populated_songs(
    requires_network: None,
) -> None:
    songs = Youtube().search("never gonna give you up", max_results=5)
    assert len(songs) == 5
    for song in songs:
        assert song["title"].strip()
        assert song["video_id"]
        assert song["duration"] >= 0


def test_youtube_adapter_satisfies_music_source_protocol(
    mocker: MockerFixture,
) -> None:
    mocker.patch("ytmusic_tui.music.youtube.YoutubeDL")
    assert isinstance(Youtube(), MusicSourceProtocol)
