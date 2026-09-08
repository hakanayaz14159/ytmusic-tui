# Search, streams, and playback

`Youtube` (`ytmusic_tui.music.youtube`) runs yt-dlp search and Google suggest, and returns `Song` values. Search and suggest caches are in-memory dicts: no LRU, nothing on disk.

The adapter sets yt-dlp's player client to `android`. The default `android-sdkless` URLs return 403 when VLC sends `Range: bytes=0-`. The format selector prefers audio. If yt-dlp returns a format list instead of one URL, the adapter picks the best audio-only format and merges extractor headers with format headers.

Search and suggest run on Textual worker threads. A generation counter ignores stale results and errors. Submit, Escape, and query edits cancel pending suggestions.

## Playing a track

1. Bump a playback generation.
2. A worker calls `PlaybackService.resolve_stream`.
3. Under the player lock, `prepare_stream` starts VLC and sets volume. It does not update UI state yet.
4. If that generation is still current, commit the song. Otherwise stop the stream that was just prepared.
5. A tick updates position, reports failures, and advances the queue, except while another track is loading.

VLC plays through `AudioStreamProxy` on localhost. The proxy adds the CDN headers and Range requests VLC cannot send. Proxy shutdown runs on a background thread so the UI does not wait on the HTTP server poll. VLC closing the localhost connection is ignored (broken pipe); it is not a proxy failure.

A missing system libVLC is a startup error with install instructions. `--help` and `--version` do not need VLC.

The app stops playback on exit. A failed stream resolve leaves the current track playing. A failed engine start clears the playing state. Adapter errors become domain errors and notifications.
