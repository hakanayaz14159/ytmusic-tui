# Contributing

Use [uv](https://docs.astral.sh/uv/) in a checkout. End users install with pipx, `uv tool`, or pip; they do not need uv.

```bash
uv sync --all-groups
uv run pytest
uv run pytest --cov=ytmusic_tui --cov-report=term-missing
uv run ruff format --check ytmusic_tui/ tests/
uv run ruff check ytmusic_tui/ tests/
uv run mypy ytmusic_tui/ tests/
uv run ruff format ytmusic_tui/ tests/
uv run ruff check --fix ytmusic_tui/ tests/
uv run textual run --dev ytmusic_tui/main.py
```

When YouTube breaks extraction in a checkout: `uv lock --upgrade-package yt-dlp`.

Checks, test fixtures, and commit style are in [`AGENTS.md`](AGENTS.md). Playback notes (android client, VLC proxy) are in [`docs/playback.md`](docs/playback.md).

## Tests

The suite is offline: YouTube and audio adapters are mocked, databases are in-memory SQLite, and the TUI is driven by Textual's headless pilot.

Live YouTube contract checks are opt-in:

```bash
uv run pytest tests/test_youtube_contract.py -m network
```

## Architecture

Domain types do not import Textual, VLC, yt-dlp, or Peewee. Adapters implement `ytmusic_tui.music.ports`. Services take those protocols. The TUI calls services and reads `AppState`.

```
ytmusic_tui/
├── db/             # Persistence adapters (Peewee SQLite models & repositories)
│   ├── user.py     # Profile & user account entities
│   ├── playlist.py # Playlists & track associations
│   └── song.py     # Track metadata persistence
├── music/          # Domain types, ports, services, external adapters
│   ├── types.py    # Domain models and TypedDicts
│   ├── ports.py    # Protocols implemented by the adapters
│   ├── services/   # Search, playback, playlist, account, settings use cases
│   ├── youtube.py  # yt-dlp adapter for search and stream extraction
│   ├── stream_proxy.py # Local HTTP bridge for stream request headers
│   └── state.py    # Reactive application state
├── tui/            # Presentation layer (Textual shell, modes, widgets)
│   ├── app.py      # YTMusicApp: the Textual application and playback coordinator
│   ├── access.py   # Typed accessor for the running app (breaks import cycle)
│   ├── shell.py    # Persistent chrome: modes, now-playing, status
│   ├── modes/      # Search, Queue, Playlists, Profiles, Settings
│   ├── widgets/    # Mode bar, song table, now playing
│   └── modals/     # Help, prompts, confirmations
└── main.py         # Application entry point and CLI command
```

## Bug reports

`YTMUSIC_LOG=1 ytmusic-tui` writes a timestamped log next to the database. Logs redact query strings from stream URLs and the `Cookie` and `Authorization` headers; skim a log before attaching it to an issue.

## Releasing

PyPI accepts each version once. A GitHub Release whose tag matches `__version__` (for example `v0.1.1` after bumping [`ytmusic_tui/__init__.py`](ytmusic_tui/__init__.py) to `0.1.1`) runs [`.github/workflows/publish.yml`](.github/workflows/publish.yml) and uploads the wheel.
