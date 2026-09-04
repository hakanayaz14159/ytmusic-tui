# YouTube & Audio Architecture Documentation

## Overview

This document specifies the audio extraction, streaming, and playback architecture for the YTMusic CLI music player. The application interacts with YouTube exclusively as an audio streaming and metadata source (no video playback or rendering).

---

## Core Operations

The YouTube integration layer (`ytmusic_cli.music.youtube.Youtube`) provides 5 core capabilities:

1. **Search**: Query YouTube videos and convert results into standard `Song` domain entities.
2. **Audio Stream Extraction**: Obtain direct audio stream URLs (e.g. m4a/opus) for real-time playback.
3. **Metadata Extraction**: Fetch detailed track information including title, artist/uploader, duration, view count, and album/playlist details.
4. **Local Audio Download**: Download audio-only tracks to local disk with embedded metadata (ID3/tags) for offline playback.
5. **Live Stream Detection**: Detect live broadcast status and extract HLS/DASH audio manifests.

---

## Component Architecture

```
+-------------------------------------------------------------+
|                      Presentation Layer                     |
|                 Textual TUI (App & Widgets)                 |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                      Application Layer                      |
|       SearchService | PlaybackService | DownloadService     |
+---------------+------------------------------+--------------+
                |                              |
                v                              v
+-------------------------------+ +---------------------------+
|      YouTube Adapter Layer    | |    Audio Playback Engine  |
| (yt-dlp Python API Wrapper)   | |        (python-vlc)       |
+-------------------------------+ +---------------------------+
                |                              |
                v                              v
+-------------------------------+ +---------------------------+
|    YouTube Audio Streams /    | |   System Audio Output /   |
|         Local Storage         | |       libvlc Driver       |
+-------------------------------+ +---------------------------+
```

---

## Technical Specifications

### 1. Audio Stream Extraction

- **Format Selection**: Configured to extract audio-only streams using `bestaudio/best`.
- **Bitrate / Codec**: Prefers high-bitrate AAC/m4a or Opus streams for minimal bandwidth and optimal sound fidelity.
- **Direct Streaming**: yt-dlp resolves CDN direct stream URLs, which are passed directly to `python-vlc` for low-latency playback without intermediate buffering files.

### 2. Audio Playback Engine (`python-vlc`)

- Utilizes `python-vlc` binding to the host system's `libvlc`.
- Supports direct streaming of HTTP/HTTPS audio URLs as well as local media files (`file://`).
- Provides asynchronous playback control: play, pause, resume, seek, stop, and volume normalization.
- Handles audio events (end of track, buffer underflow, error states) to trigger automated track progression in playlists.

### 3. Local Audio Download

- Triggered by user request to download songs or entire playlists.
- Utilizes yt-dlp's audio extraction pipeline:
  ```python
  download_options = {
      'format': 'bestaudio/best',
      'extractaudio': True,
      'audioformat': 'mp3',  # or m4a/flac based on profile preferences
      'audioquality': '192K',
      'outtmpl': 'downloads/%(artist)s - %(title)s.%(ext)s',
  }
  ```
- Saved audio tracks are indexed in the local SQLite database (`Song.local_path`) for immediate offline playback.

### 4. Caching & Rate Limiting

- **Search Cache**: In-memory LRU cache of search queries to avoid repeated YouTube searches for identical strings.
- **Metadata Cache**: In-memory cache of video metadata keyed by YouTube video ID.
- **Throttling**: Configurable request sleep intervals (`sleep_interval=1`) to prevent IP rate-limiting from YouTube endpoints.

---

## Test-Driven Design (TDD) Testing Strategy

To adhere to strict TDD and ensure fast, deterministic tests without network dependencies:

1. **Unit Tests with `mock_youtube`**:
   - The test suite provides a `mock_youtube` fixture in `tests/conftest.py` returning structured `Song` dictionaries and dummy stream URLs.
   - Any service or widget interacting with YouTube must be testable using this mock without issuing real network requests.

2. **Playback Tests with `mock_player`**:
   - Audio playback is decoupled from system audio hardware using `mock_player`.
   - Tests assert player state transitions (idle -> playing -> paused -> stopped) without producing sound or requiring an active sound server (PulseAudio/PipeWire/ALSA).

3. **End-to-End Smoke Verification**:
   - Live integration tests against real YouTube endpoints can be run selectively via `test_youtube.py` with explicit opt-in.
