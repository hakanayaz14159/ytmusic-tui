import json
import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from yt_dlp import YoutubeDL

from ytmusic_cli.consts import DEFAULT_SUGGEST_LIMIT
from ytmusic_cli.exceptions import (
    StreamExtractionError,
    SuggestionError,
    TrackNotFoundError,
    YTMusicError,
)
from ytmusic_cli.utils.log import redact_headers, redact_url

from .types import AudioStream, Song

logger = logging.getLogger(__name__)

_AUDIO_FORMAT = "bestaudio[protocol^=http]/bestaudio/best"
_SUGGEST_ENDPOINT = "https://suggestqueries.google.com/complete/search"
_SUGGEST_TIMEOUT_SECONDS = 5
_SUGGEST_USER_AGENT = "Mozilla/5.0"


def _string_field(value: object, default: str) -> str:
    if isinstance(value, str) and value:
        return value
    return default


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _duration_seconds(value: object) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float | str):
        try:
            return max(0, int(float(value)))
        except (ValueError, OverflowError):
            return 0
    return 0


def _http_headers(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise StreamExtractionError("Invalid stream headers")
    headers: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise StreamExtractionError("Invalid stream headers")
        headers[key] = item
    return headers


def _parse_suggest_payload(payload: object, max_results: int) -> list[str]:
    if not isinstance(payload, list):
        raise SuggestionError("Unexpected suggest payload")
    try:
        raw = payload[1]
    except IndexError:
        raise SuggestionError("Unexpected suggest payload") from None
    if isinstance(raw, str | bytes) or not isinstance(raw, Sequence):
        raise SuggestionError("Unexpected suggest payload")
    suggestions: list[str] = []
    for item in raw:
        if isinstance(item, str):
            suggestions.append(item)
            if len(suggestions) >= max_results:
                break
    return suggestions


def _best_audio_stream(
    formats: object, top_headers: dict[str, str]
) -> AudioStream | None:
    if not isinstance(formats, list):
        return None
    candidates: list[Mapping[str, object]] = []
    # yt-dlp returns formats ranked from worst to best.
    for value in reversed(formats):
        if not isinstance(value, Mapping):
            raise StreamExtractionError("Invalid stream format")
        fmt = cast("Mapping[str, object]", value)
        codec = _optional_string(fmt.get("acodec"))
        if codec is not None and codec != "none" and fmt.get("url"):
            candidates.append(fmt)
    if not candidates:
        return None
    selected = next(
        (fmt for fmt in candidates if fmt.get("vcodec") == "none"), candidates[0]
    )
    url = selected.get("url")
    if not isinstance(url, str):
        raise StreamExtractionError("Invalid stream URL")
    return AudioStream(
        url=url,
        http_headers=top_headers | _http_headers(selected.get("http_headers")),
    )


def _log_stream(video_id: str, stream: AudioStream) -> None:
    logger.info(
        "get_stream video_id=%s url=%s headers=%s",
        video_id,
        redact_url(stream["url"]),
        list(redact_headers(stream["http_headers"])),
    )


class Youtube:
    """YouTube adapter for search, query suggestions, and stream resolution."""

    def __init__(self, options: Mapping[str, object] | None = None) -> None:
        self._base_options: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
            "format": _AUDIO_FORMAT,
            "extractor_args": {
                "youtube": {"player_client": ["android"]},
            },
        }
        if options:
            self._base_options.update(options)

        self._search_cache: dict[str, list[Song]] = {}
        self._suggest_cache: dict[str, list[str]] = {}

    def _options(self, **overrides: object) -> dict[str, object]:
        merged = dict(self._base_options)
        merged.update(overrides)
        return merged

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        cache_key = f"{query}:{max_results}"
        if cache_key in self._search_cache:
            logger.debug("search cache hit query=%r", query)
            return self._search_cache[cache_key]

        try:
            search_query = f"ytsearch{max_results}:{query}"

            with YoutubeDL(self._options(extract_flat="in_playlist")) as ydl:
                search_results: object = ydl.extract_info(search_query, download=False)

                if not isinstance(search_results, Mapping):
                    logger.info("search query=%r results=0", query)
                    return []

                entries: object = search_results.get("entries")
                if not isinstance(entries, Iterable) or isinstance(
                    entries, str | bytes | Mapping
                ):
                    return []
                songs: list[Song] = []
                for entry in entries:
                    if entry:
                        song = self._convert_entry_to_song(entry)
                        if song:
                            songs.append(song)

                self._search_cache[cache_key] = songs
                logger.info("search query=%r results=%s", query, len(songs))
                return songs

        except YTMusicError:
            logger.exception("search failed query=%r", query)
            raise
        except Exception as e:
            logger.exception("search failed query=%r", query)
            raise StreamExtractionError(
                f"Search failed for query '{query}': {e!s}"
            ) from e

    def suggest(
        self, query: str, max_results: int = DEFAULT_SUGGEST_LIMIT
    ) -> list[str]:
        cache_key = f"{query}:{max_results}"
        if cache_key in self._suggest_cache:
            logger.debug("suggest cache hit query=%r", query)
            return self._suggest_cache[cache_key]

        try:
            params = urlencode({"client": "firefox", "ds": "yt", "q": query})
            request = Request(
                f"{_SUGGEST_ENDPOINT}?{params}",
                headers={"User-Agent": _SUGGEST_USER_AGENT},
            )
            with urlopen(request, timeout=_SUGGEST_TIMEOUT_SECONDS) as response:
                raw = response.read()
            payload: object = json.loads(raw.decode())
            suggestions = _parse_suggest_payload(payload, max_results)
            self._suggest_cache[cache_key] = suggestions
            logger.info("suggest query=%r results=%s", query, len(suggestions))
            return suggestions
        except YTMusicError:
            logger.exception("suggest failed query=%r", query)
            raise
        except Exception as err:
            logger.exception("suggest failed query=%r", query)
            raise SuggestionError(
                f"Suggest failed for query '{query}': {err!s}"
            ) from err

    def get_stream(self, video_id: str) -> AudioStream:
        try:
            video_url = self._normalize_video_url(video_id)

            with YoutubeDL(self._options()) as ydl:
                info: object = ydl.extract_info(video_url, download=False)

                if not isinstance(info, Mapping) or not info:
                    raise TrackNotFoundError(
                        f"Could not extract info for video: {video_id}"
                    )

                top_headers = _http_headers(info.get("http_headers"))

                if "url" in info:
                    url = info["url"]
                    if not isinstance(url, str) or not url:
                        raise StreamExtractionError("Invalid stream URL")
                    stream = AudioStream(
                        url=url,
                        http_headers=top_headers,
                    )
                    _log_stream(video_id, stream)
                    return stream
                fallback_stream = _best_audio_stream(info.get("formats"), top_headers)
                if fallback_stream is not None:
                    _log_stream(video_id, fallback_stream)
                    return fallback_stream

                raise TrackNotFoundError("No audio stream URL found")

        except YTMusicError:
            logger.exception("get_stream failed video_id=%s", video_id)
            raise
        except Exception as e:
            logger.exception("get_stream failed video_id=%s", video_id)
            raise StreamExtractionError(
                f"Failed to get stream URL for video {video_id}: {e!s}"
            ) from e

    def _convert_entry_to_song(self, entry: object) -> Song | None:
        if not isinstance(entry, Mapping):
            return None
        raw_id = entry.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            return None

        title = _string_field(entry.get("title"), "Unknown Title")
        uploader = _optional_string(entry.get("uploader")) or entry.get("channel")
        artist = _string_field(uploader, "Unknown Uploader")
        album = _optional_string(entry.get("album")) or _optional_string(
            entry.get("playlist_title")
        )
        return Song(
            video_id=raw_id,
            title=title,
            artist=artist,
            album=album,
            duration=_duration_seconds(entry.get("duration")),
        )

    def _normalize_video_url(self, video_id: str) -> str:
        if video_id.startswith(("http://", "https://")):
            return video_id

        if re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
            return f"https://www.youtube.com/watch?v={video_id}"

        video_id_match = re.search(r"(?:v=|/)([a-zA-Z0-9_-]{11})", video_id)
        if video_id_match:
            return f"https://www.youtube.com/watch?v={video_id_match.group(1)}"

        return video_id
