import re
from typing import Any

from yt_dlp import YoutubeDL

from ytmusic_cli.exceptions import (
    StreamExtractionError,
    TrackNotFoundError,
    YTMusicError,
)

from .types import AudioStream, Song


class Youtube:
    """
    YouTube class providing search, metadata extraction, and audio streaming capabilities.

    This class implements 5 core operations:
    1. Search - Search for videos on YouTube
    2. Stream Sound - Get audio stream URLs for real-time playback
    3. GetMetadata - Extract comprehensive metadata from videos
    4. Stream operations - Provide stream URLs for audio playback
    5. Real-time streaming - Support live audio streaming like YouTube does

    Note: yt-dlp doesn't natively support byte-level streaming through its Python API.
    For real streaming, you would need to use the stream URLs with an external HTTP client
    or audio player that supports progressive streaming.
    """

    def __init__(self, options: dict[str, Any] | None = None) -> None:
        """
        Initialize YouTube client with configurable options.

        Args:
            options: Optional yt-dlp configuration options
        """
        default_options = {
            "quiet": True,
            "no_warnings": True,
            "extractaudio": True,
            "audioformat": "best",
            "outtmpl": "%(title)s.%(ext)s",
            "format": "bestaudio[protocol^=http]/bestaudio/best",
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                }
            },
            # Optimize for streaming
            "buffersize": 1024 * 16,  # 16KB buffer
            "http_chunk_size": 1024 * 16,
            # Rate limiting and headers
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "user_agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
        }

        if options:
            default_options.update(options)

        self.ydl = YoutubeDL(default_options)
        self._search_cache: dict[str, list[Song]] = {}
        self._metadata_cache: dict[str, dict[str, Any]] = {}

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        """
        Search for videos on YouTube and return them as Song objects.

        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 10)

        Returns:
            List of Song objects matching the search query

        Raises:
            StreamExtractionError: If search fails
        """
        # Check cache first
        cache_key = f"{query}:{max_results}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        try:
            # Use yt-dlp's built-in search functionality
            search_query = f"ytsearch{max_results}:{query}"

            with YoutubeDL(self.ydl.params) as ydl:
                # Extract info without downloading
                search_results = ydl.extract_info(search_query, download=False)

                if not search_results or "entries" not in search_results:
                    return []

                songs = []
                for entry in search_results["entries"]:
                    if entry:  # Sometimes entries can be None
                        song = self._convert_entry_to_song(entry)
                        if song:
                            songs.append(song)

                # Cache the results
                self._search_cache[cache_key] = songs
                return songs

        except YTMusicError:
            raise
        except Exception as e:
            raise StreamExtractionError(
                f"Search failed for query '{query}': {e!s}"
            ) from e

    def get_stream(
        self,
        video_id: str,
        quality: str = "bestaudio[protocol^=http]/bestaudio",
    ) -> AudioStream:
        """
        Get the direct stream URL and associated HTTP headers for a YouTube video.

        Args:
            video_id: YouTube video ID or URL
            quality: Audio quality preference ('bestaudio', format code, etc.)

        Returns:
            AudioStream containing direct stream URL and HTTP request headers

        Raises:
            TrackNotFoundError: If video info or audio stream is missing
            StreamExtractionError: If URL extraction fails
        """
        try:
            video_url = self._normalize_video_url(video_id)

            # Configure yt-dlp for URL extraction
            url_options = self.ydl.params.copy()
            url_options["format"] = quality

            with YoutubeDL(url_options) as ydl:
                info = ydl.extract_info(video_url, download=False)

                if not info:
                    raise TrackNotFoundError(
                        f"Could not extract info for video: {video_id}"
                    )

                top_headers: dict[str, str] = dict(info.get("http_headers") or {})

                # Get the URL from the selected format or top-level info
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

    def get_stream_url(self, video_id: str, quality: str = "bestaudio") -> str:
        """
        Get the direct stream URL for a YouTube video's audio.

        Args:
            video_id: YouTube video ID or URL
            quality: Audio quality preference ('bestaudio', 'worstaudio', or format code)

        Returns:
            Direct URL to the audio stream
        """
        return self.get_stream(video_id, quality=quality)["url"]

    def stream_sound(self, video_id: str, _chunk_size: int = 8192) -> str:
        """
        Get the stream URL for audio streaming.

        Note: yt-dlp doesn't provide native byte-level streaming in its Python API.
        This method returns the direct stream URL that can be used with external
        HTTP clients (like requests, urllib, or audio players) for real-time streaming.

        Args:
            video_id: YouTube video ID or URL
            chunk_size: Chunk size hint (not used directly by yt-dlp)

        Returns:
            Direct stream URL that can be used for streaming

        Raises:
            TrackNotFoundError: If stream URL cannot be resolved
            StreamExtractionError: If streaming URL extraction fails

        Example:
            >>> youtube = Youtube()
            >>> stream_url = youtube.stream_sound("dQw4w9WgXcQ")
            >>> # Use stream_url with requests, urllib, or media player for actual streaming
        """
        try:
            # Get the stream URL for the video
            stream_url = self.get_stream_url(video_id, quality="bestaudio")

            if not stream_url:
                raise TrackNotFoundError(
                    f"Could not get stream URL for video: {video_id}"
                )

            return stream_url

        except YTMusicError:
            raise
        except Exception as e:
            raise StreamExtractionError(
                f"Failed to get stream URL for video {video_id}: {e!s}"
            ) from e

    def get_metadata(self, video_id: str) -> dict[str, Any]:
        """
        Extract comprehensive metadata from a YouTube video.

        Args:
            video_id: YouTube video ID or URL

        Returns:
            Dictionary containing video metadata including:
            - title, artist, album, duration, url
            - view_count, upload_date, description
            - thumbnail, channel_info, audio_quality

        Raises:
            TrackNotFoundError: If video info cannot be extracted
            StreamExtractionError: If metadata extraction fails
        """
        # Check cache first
        if video_id in self._metadata_cache:
            return self._metadata_cache[video_id]

        try:
            video_url = self._normalize_video_url(video_id)

            with YoutubeDL(self.ydl.params) as ydl:
                info = ydl.extract_info(video_url, download=False)

                if not info:
                    raise TrackNotFoundError(
                        f"Could not extract info for video: {video_id}"
                    )

                # Extract comprehensive metadata
                metadata = {
                    # Basic Song info
                    "id": info.get("id", video_id),
                    "title": info.get("title", "Unknown Title"),
                    "artist": info.get(
                        "uploader", info.get("channel", "Unknown Artist")
                    ),
                    "album": info.get("album") or info.get("playlist_title"),
                    "duration": int(info.get("duration", 0)),
                    "url": f"https://www.youtube.com/watch?v={info.get('id', video_id)}",
                    # Extended metadata
                    "description": info.get("description", ""),
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("like_count", 0),
                    "upload_date": info.get("upload_date", ""),
                    "uploader": info.get("uploader", ""),
                    "channel_id": info.get("channel_id", ""),
                    "channel_url": info.get("channel_url", ""),
                    "thumbnail": info.get("thumbnail", ""),
                    "thumbnails": info.get("thumbnails", []),
                    # Audio quality information
                    "audio_formats": self._extract_audio_formats(
                        info.get("formats", [])
                    ),
                    "best_audio_format": self._get_best_audio_format(
                        info.get("formats", [])
                    ),
                    # Additional metadata
                    "categories": info.get("categories", []),
                    "tags": info.get("tags", []),
                    "live_status": info.get("live_status", "not_live"),
                    "availability": info.get("availability", "public"),
                }

                # Cache the metadata
                self._metadata_cache[video_id] = metadata
                return metadata

        except YTMusicError:
            raise
        except Exception as e:
            raise StreamExtractionError(
                f"Failed to get metadata for video {video_id}: {e!s}"
            ) from e

    def get_live_stream_info(self, video_id: str) -> dict[str, Any]:
        """
        Get information about live streams for real-time streaming support.

        Args:
            video_id: YouTube video ID or URL

        Returns:
            Dictionary with live stream information including HLS/DASH URLs
        """
        try:
            metadata = self.get_metadata(video_id)

            if metadata.get("live_status") == "is_live":
                video_url = self._normalize_video_url(video_id)

                with YoutubeDL(self.ydl.params) as ydl:
                    info = ydl.extract_info(video_url, download=False)

                    live_info = {
                        "is_live": True,
                        "live_status": info.get("live_status"),
                        "hls_url": None,
                        "dash_url": None,
                        "formats": [],
                    }

                    # Extract live streaming formats
                    for fmt in info.get("formats", []):
                        if fmt.get("protocol") in ["m3u8", "m3u8_native"]:
                            live_info["hls_url"] = fmt.get("url")
                        elif fmt.get("protocol") == "http_dash_segments":
                            live_info["dash_url"] = fmt.get("url")

                        if fmt.get("acodec") != "none":
                            live_info["formats"].append(
                                {
                                    "format_id": fmt.get("format_id"),
                                    "quality": fmt.get("quality", "unknown"),
                                    "url": fmt.get("url"),
                                    "protocol": fmt.get("protocol"),
                                    "acodec": fmt.get("acodec"),
                                    "abr": fmt.get("abr"),
                                }
                            )

                    return live_info
            else:
                return {"is_live": False, "live_status": metadata.get("live_status")}

        except YTMusicError:
            raise
        except Exception as e:
            raise StreamExtractionError(
                f"Failed to get live stream info for video {video_id}: {e!s}"
            ) from e

    def download_audio(self, video_id: str, output_path: str | None = None) -> str:
        """
        Download audio file using yt-dlp's native download capabilities.

        This is the proper way to use yt-dlp for downloading audio files.

        Args:
            video_id: YouTube video ID or URL
            output_path: Optional output path for the downloaded file

        Returns:
            Path to the downloaded audio file

        Raises:
            StreamExtractionError: If download fails
        """
        try:
            video_url = self._normalize_video_url(video_id)

            # Configure options for audio download
            download_options = self.ydl.params.copy()
            download_options.update(
                {
                    "format": "bestaudio/best",
                    "extractaudio": True,
                    "audioformat": "mp3",
                    "audioquality": "192K",
                }
            )

            if output_path:
                download_options["outtmpl"] = output_path

            with YoutubeDL(download_options) as ydl:
                ydl.download([video_url])

                # Get the output filename
                info = ydl.extract_info(video_url, download=False)
                filename = ydl.prepare_filename(info)

                return filename

        except YTMusicError:
            raise
        except Exception as e:
            raise StreamExtractionError(
                f"Failed to download audio for video {video_id}: {e!s}"
            ) from e

    def _convert_entry_to_song(self, entry: dict[str, Any]) -> Song | None:
        """Convert a yt-dlp entry to a Song object."""
        try:
            # Extract video ID from URL or use the provided ID
            video_id = entry.get("id")
            if not video_id:
                return None

            return Song(
                id=hash(video_id),  # Convert string ID to int for compatibility
                title=entry.get("title", "Unknown Title"),
                artist=entry.get("uploader", entry.get("channel", "Unknown Artist")),
                album=entry.get("album") or entry.get("playlist_title"),
                duration=int(entry.get("duration", 0)),
                url=f"https://www.youtube.com/watch?v={video_id}",
            )
        except Exception:
            return None

    def _normalize_video_url(self, video_id: str) -> str:
        """Convert video ID or various URL formats to standard YouTube URL."""
        # If it's already a full URL, return as is
        if video_id.startswith(("http://", "https://")):
            return video_id

        # If it's just a video ID, create the full URL
        if re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
            return f"https://www.youtube.com/watch?v={video_id}"

        # Try to extract video ID from various URL formats
        video_id_match = re.search(r"(?:v=|/)([a-zA-Z0-9_-]{11})", video_id)
        if video_id_match:
            return f"https://www.youtube.com/watch?v={video_id_match.group(1)}"

        # If all else fails, return as is and let yt-dlp handle it
        return video_id

    def _extract_audio_formats(
        self, formats: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract and categorize available audio formats."""
        audio_formats = []
        for fmt in formats:
            if fmt.get("acodec") != "none":
                audio_formats.append(
                    {
                        "format_id": fmt.get("format_id"),
                        "ext": fmt.get("ext"),
                        "acodec": fmt.get("acodec"),
                        "abr": fmt.get("abr"),
                        "asr": fmt.get("asr"),
                        "filesize": fmt.get("filesize"),
                        "quality": fmt.get("quality", "unknown"),
                    }
                )
        return audio_formats

    def _get_best_audio_format(
        self, formats: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Get the best available audio format."""
        audio_formats = self._extract_audio_formats(formats)
        if not audio_formats:
            return None

        # Sort by audio bitrate (higher is better)
        audio_formats.sort(key=lambda x: x.get("abr", 0) or 0, reverse=True)
        return audio_formats[0] if audio_formats else None

    def clear_cache(self) -> None:
        """Clear all internal caches."""
        self._search_cache.clear()
        self._metadata_cache.clear()

    def __enter__(self) -> "Youtube":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit - cleanup resources."""
        self.clear_cache()
