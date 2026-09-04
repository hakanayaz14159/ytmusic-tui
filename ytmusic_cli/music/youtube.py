import re
from typing import Any

from yt_dlp import YoutubeDL

from ytmusic_cli.exceptions import (
    StreamExtractionError,
    TrackNotFoundError,
    YTMusicError,
)

from .types import AudioStream, Song

_AUDIO_FORMAT = "bestaudio[protocol^=http]/bestaudio/best"


class Youtube:
    """yt-dlp adapter for search and audio stream resolution."""

    def __init__(self, options: dict[str, Any] | None = None) -> None:
        self._base_options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
            "format": _AUDIO_FORMAT,
        }
        if options:
            self._base_options.update(options)

        self._search_cache: dict[str, list[Song]] = {}

    def _options(self, **overrides: Any) -> dict[str, Any]:
        merged = dict(self._base_options)
        merged.update(overrides)
        return merged

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        cache_key = f"{query}:{max_results}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        try:
            search_query = f"ytsearch{max_results}:{query}"

            with YoutubeDL(self._options(extract_flat="in_playlist")) as ydl:
                search_results = ydl.extract_info(search_query, download=False)

                if not search_results or "entries" not in search_results:
                    return []

                songs = []
                for entry in search_results["entries"]:
                    if entry:
                        song = self._convert_entry_to_song(entry)
                        if song:
                            songs.append(song)

                self._search_cache[cache_key] = songs
                return songs

        except YTMusicError:
            raise
        except Exception as e:
            raise StreamExtractionError(
                f"Search failed for query '{query}': {e!s}"
            ) from e

    def get_stream(self, video_id: str) -> AudioStream:
        try:
            video_url = self._normalize_video_url(video_id)

            with YoutubeDL(self._options()) as ydl:
                info = ydl.extract_info(video_url, download=False)

                if not info:
                    raise TrackNotFoundError(
                        f"Could not extract info for video: {video_id}"
                    )

                top_headers: dict[str, str] = dict(info.get("http_headers") or {})

                if "url" in info:
                    return AudioStream(
                        url=info["url"],
                        http_headers=top_headers,
                    )
                elif info.get("formats"):
                    for fmt in info["formats"]:
                        if fmt.get("acodec") != "none" and fmt.get("url"):
                            fmt_headers: dict[str, str] = dict(
                                fmt.get("http_headers") or top_headers
                            )
                            return AudioStream(
                                url=fmt["url"],
                                http_headers=fmt_headers,
                            )

                raise TrackNotFoundError("No audio stream URL found")

        except YTMusicError:
            raise
        except Exception as e:
            raise StreamExtractionError(
                f"Failed to get stream URL for video {video_id}: {e!s}"
            ) from e

    def _convert_entry_to_song(self, entry: dict[str, Any]) -> Song | None:
        raw_id = entry.get("id")
        if not raw_id:
            return None

        duration = entry.get("duration")
        return Song(
            video_id=str(raw_id),
            title=entry.get("title", "Unknown Title"),
            artist=entry.get("uploader", entry.get("channel", "Unknown Artist")),
            album=entry.get("album") or entry.get("playlist_title"),
            duration=int(duration) if duration is not None else 0,
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
