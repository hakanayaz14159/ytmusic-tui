# YouTube and audio architecture

This document describes the implemented player. Offline downloads, local-file playback, seeking, metadata embedding, and YouTube account synchronization are future work.

## Implemented capabilities

- Keyword search through yt-dlp, converted to typed `Song` values.
- Query suggestions through the YouTube suggestion endpoint.
- Audio stream resolution with the request headers required by the CDN.
- VLC playback, pause/resume, volume, position reporting, and queue progression.
- Local SQLite profiles and ordered playlists. Saved playlists contain unique video IDs; the playback queue can contain repeated tracks.

## Search and stream resolution

`SearchService` validates queries and delegates to `MusicSourceProtocol`. The `Youtube` adapter owns yt-dlp options, metadata validation, and in-memory search/suggestion caches. These caches are dictionaries; there is no LRU eviction or persistent metadata cache.

The adapter pins yt-dlp's android player client. yt-dlp's default android-sdkless URLs 403 on `Range: bytes=0-`, which VLC always sends. Callers may still supply explicit options. The format selector prefers audio streams. When yt-dlp returns a format list instead of a selected URL, the adapter prefers the highest-ranked audio-only format and combines inherited headers with format-specific headers.

Network requests run in Textual thread workers. Search request generations prevent a late result or error from replacing a newer search. Submission, Escape, and query changes invalidate pending suggestions.

## Playback path

1. A selection starts a playback request with a generation identifier.
2. A worker resolves the stream through `PlaybackService.resolve_stream`.
3. Under the app's player lock, `prepare_stream` starts the engine and applies volume without publishing playback state.
4. The UI commits the song and playback state only if the request is still current. Obsolete prepared streams are stopped.
5. A periodic playback tick updates position, detects failures, and advances the queue. It does not advance while another track is loading.

`VLCPlayer` sends VLC to a localhost HTTP proxy. The proxy forwards stream headers and byte ranges to the upstream URL, supporting headers that VLC cannot reliably supply itself. Proxy shutdown runs on a cleanup thread so stopping or replacing a track does not wait for the HTTP server polling interval on the UI thread.

The app stops playback when it exits. Adapter errors are wrapped in domain errors and surfaced as notifications. Stream-resolution failure preserves existing playback; failed engine startup clears the stale playing state.

## Persistence

Repository adapters convert Peewee rows into domain types. Playlist replacement and recursive deletion use transactions. Deleting a playlist or profile also deletes its membership rows; failed replacement preserves the original playlist. Duplicate additions are rejected before modifying stored song metadata.

Profile changes clear the working playlist. In-flight load/save completions check the initiating profile before changing the visible queue or working selection. Confirmations retain the target shown when the dialog opened.

## Verification

The default pytest suite uses mocked YouTube and audio adapters, in-memory SQLite, and Textual's headless pilot. Thread events coordinate concurrency regressions without hard sleeps.

The optional `network` tests check live YouTube behavior and are excluded from the default run. Passing offline tests does not establish current CDN availability or working audio on a particular machine; those depend on YouTube, installed libVLC, and the host audio device.

See [the feature reliability review](docs/feature-reliability-review.md) for acceptance criteria and audit results.
