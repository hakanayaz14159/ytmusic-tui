# Contributor notes

`ytmusic_tui.music.types` must not import Textual, VLC, yt-dlp, or Peewee. Adapters implement `ytmusic_tui.music.ports`. Setup, layout, and releasing are in [`CONTRIBUTING.md`](CONTRIBUTING.md). Search, streams, and the VLC proxy are in [`docs/playback.md`](docs/playback.md).

## Checks

- Tests first. No `time.sleep` or `asyncio.sleep` in tests. Use `test_db`, `mock_youtube`, `mock_player`, and reset `AppState`.
- `uv run pytest`
- `uv run mypy ytmusic_tui/ tests/`
- `uv run ruff check ytmusic_tui/ tests/`
- `uv run ruff format --check ytmusic_tui/ tests/`
- Conventional Commits. Diffs stay limited to the requested change.
