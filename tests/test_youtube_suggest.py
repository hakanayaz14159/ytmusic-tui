"""Unit tests for Youtube.suggest with mocked HTTP."""

import json
from unittest.mock import MagicMock
from urllib.error import URLError

import pytest
from pytest_mock import MockerFixture

from ytmusic_cli.exceptions import SuggestionError
from ytmusic_cli.music.youtube import Youtube


@pytest.fixture
def youtube_no_init(mocker: MockerFixture) -> Youtube:
    mocker.patch("ytmusic_cli.music.youtube.YoutubeDL")
    return Youtube()


def _patch_urlopen(mocker: MockerFixture, payload: object) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return mocker.patch("ytmusic_cli.music.youtube.urlopen", return_value=response)


def test_suggest_returns_query_strings_from_payload(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    _patch_urlopen(mocker, ["beat", ["beatles", "beatles yesterday", "beat it"]])

    results = youtube_no_init.suggest("beat", max_results=2)

    assert results == ["beatles", "beatles yesterday"]


def test_suggest_drops_non_string_entries(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    _patch_urlopen(mocker, ["lo", ["lofi", 12, None, "lofi girl"]])

    results = youtube_no_init.suggest("lo", max_results=8)

    assert results == ["lofi", "lofi girl"]


def test_suggest_empty_list_is_success(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    _patch_urlopen(mocker, ["zz", []])

    assert youtube_no_init.suggest("zz") == []


def test_suggest_bad_json_raises_suggestion_error(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    response = MagicMock()
    response.read.return_value = b"not-json"
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    mocker.patch("ytmusic_cli.music.youtube.urlopen", return_value=response)

    with pytest.raises(SuggestionError, match="beat") as exc_info:
        youtube_no_init.suggest("beat")
    assert exc_info.value.__cause__ is not None


@pytest.mark.parametrize(
    "payload",
    [
        {"suggestions": ["beatles"]},
        ["beat"],
        ["beat", "beatles"],
        ["beat", {"q": "beatles"}],
    ],
)
def test_suggest_rejects_malformed_payload(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
    payload: object,
) -> None:
    _patch_urlopen(mocker, payload)

    with pytest.raises(SuggestionError):
        youtube_no_init.suggest("beat")


def test_suggest_http_error_is_chained(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    cause = URLError("timed out")
    mocker.patch("ytmusic_cli.music.youtube.urlopen", side_effect=cause)

    with pytest.raises(SuggestionError) as exc_info:
        youtube_no_init.suggest("beat")
    assert exc_info.value.__cause__ is cause


def test_suggest_cache_skips_second_request(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    urlopen = _patch_urlopen(mocker, ["beat", ["beatles"]])

    first = youtube_no_init.suggest("beat", max_results=8)
    second = youtube_no_init.suggest("beat", max_results=8)

    assert first == ["beatles"]
    assert second == ["beatles"]
    urlopen.assert_called_once()


def test_suggest_request_targets_youtube_complete_endpoint(
    youtube_no_init: Youtube,
    mocker: MockerFixture,
) -> None:
    urlopen = _patch_urlopen(mocker, ["beat it", ["beat it"]])

    youtube_no_init.suggest("beat it", max_results=8)

    request = urlopen.call_args.args[0]
    assert "suggestqueries.google.com/complete/search" in request.full_url
    assert "client=firefox" in request.full_url
    assert "ds=yt" in request.full_url
    assert "q=beat+it" in request.full_url or "q=beat%20it" in request.full_url
    assert request.get_header("User-agent") or request.headers.get("User-Agent")
