<p align="center">
  <img src="docs/logo.svg" alt="YTMusic TUI" width="420">
</p>

# YTMusic TUI

A keyboard-driven, audio-only terminal music player for YouTube, built with Python, [Textual](https://github.com/Textualize/textual), [yt-dlp](https://github.com/yt-dlp/yt-dlp), and VLC.

Search YouTube, queue tracks, and keep local profiles and playlists — without leaving the terminal and without loading video.

> **Unofficial.** This is a personal hobby project and is not affiliated with, endorsed by, or sponsored by Google LLC, YouTube, or YouTube Music. Please read the [Disclaimer](#disclaimer) before using it.

---

## Features

- **Audio-only streaming**: resolves and plays the audio stream, so no bandwidth is spent on video.
- **Search-first TUI**: search is the landing mode; the now-playing bar stays visible in every mode.
- **Playback queue**: play, append, skip, remove, and save the queue as a playlist.
- **Local playlists**: create, edit, and open playlists backed by a local SQLite database.
- **Local profiles**: multiple profiles, each with its own preferences and playlists.

---

## Roadmap

- Offline downloads and local-file playback.
- Algorithmic recommendations, possibly.

## Not implemented

- Seeking within a track, and metadata embedding.
- YouTube sign-in and library sync. Profiles are local; they are not YouTube accounts, so your YouTube library, likes, and history are out of reach.

---

## Requirements

- **Python** 3.11 or newer
- **libVLC** on the system — the `vlc` package on Linux, [VLC](https://www.videolan.org/vlc/) on macOS and Windows
- **[pipx](https://pipx.pypa.io/)** (recommended) to install the player in its own environment

`python-vlc` is only a binding; playback fails without a system libVLC and a working audio device. You do not need [uv](https://docs.astral.sh/uv/) to install or run the player; uv is for contributors.

---

## Installation

```bash
pipx install ytmusic-player-cli
ytmusic-tui
```

From git, still without uv:

```bash
pipx install git+https://github.com/hakanayaz14159/ytmusic-tui.git
```

`pip` works the same way (`pip install git+https://...` or `pip install .`) if you would rather put the package in an existing virtualenv.

---

## Usage

```bash
ytmusic-tui            # launch the TUI
ytmusic-tui --version
ytmusic-tui --help
```

Press `?` in the app for the keymap: `1`–`5` switch modes and `/` jumps to the query field.

When YouTube breaks stream extraction, refresh yt-dlp inside the pipx environment:

```bash
pipx upgrade ytmusic-player-cli
# or only yt-dlp:
pipx runpip ytmusic-player-cli install -U yt-dlp
```

### Your data

Profiles, playlists, and track metadata stay in a local SQLite file (`~/.local/share/ytmusic-tui/ytmusic.db` on Linux). There is no account, no server, and no telemetry.

File logging is off by default. Enable it when you want to report a bug:

```bash
YTMUSIC_LOG=1 ytmusic-tui   # writes a timestamped log next to the database
```

Logs redact query strings from stream URLs and the `Cookie` and `Authorization` headers, but skim a log before attaching it to an issue.

---

## Architecture

Domain types do not import Textual, VLC, yt-dlp, or Peewee:

```
ytmusic_tui/
├── db/             # Persistence adapters (Peewee SQLite models & repositories)
│   ├── user.py     # Profile & user account entities
│   ├── playlist.py # Playlists & track associations
│   └── song.py     # Track metadata persistence
├── music/          # Domain types, ports, services, external adapters
│   ├── types.py    # Domain models and TypedDicts
│   ├── ports.py    # Protocols implemented by the adapters
│   ├── services.py # Search, playback, playlist, account, settings use cases
│   ├── youtube.py  # yt-dlp adapter for search and stream extraction
│   ├── stream_proxy.py # Local HTTP bridge for stream request headers
│   └── state.py    # Reactive application state
├── tui/            # Presentation layer (Textual shell, modes, widgets)
│   ├── shell.py    # Persistent chrome: modes, now-playing, status
│   ├── modes/      # Search, Queue, Playlists, Profiles, Settings
│   ├── widgets/    # Mode bar, song table, now playing
│   └── modals/     # Help, prompts, confirmations
└── main.py         # Application entry point and CLI command
```

[`docs/playback.md`](docs/playback.md) covers search, stream URLs, and the localhost proxy VLC uses. Contributor checks are in [`AGENTS.md`](AGENTS.md).

---

## Development

Contributors can use [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-groups
make test        # uv run pytest
make test-cov    # coverage report
make lint        # ruff format --check, ruff check, mypy
make format      # ruff format + ruff check --fix
make dev         # textual run --dev for the live console
```

The suite runs fully offline: YouTube and audio adapters are mocked, databases are in-memory SQLite, and the TUI is driven by Textual's headless pilot. The handful of live YouTube contract checks are opt-in because they depend on the network and on YouTube not having changed:

```bash
uv run pytest tests/test_youtube_contract.py -m network
```

Contributions follow test-first development, strict `mypy`, and Conventional Commits. See [`AGENTS.md`](AGENTS.md).

### Releasing

PyPI accepts each version once. A GitHub Release whose tag matches `__version__` (for example `v0.1.1` after bumping [`ytmusic_tui/__init__.py`](ytmusic_tui/__init__.py) to `0.1.1`) runs [`.github/workflows/publish.yml`](.github/workflows/publish.yml) and uploads the wheel.

---

## Project status

Alpha, and a personal project I maintain for my own listening. Bug reports and pull requests are welcome, but there is no roadmap, no release schedule, and no support commitment. Since playback depends on yt-dlp keeping up with YouTube, expect the occasional breakage and keep `yt-dlp` up to date (`pipx upgrade ytmusic-player-cli`, or `uv lock --upgrade-package yt-dlp` in a contributor checkout).

---

## Disclaimer

**Not affiliated with Google.** YTMusic TUI is an independent, unofficial project. It is not affiliated with, endorsed by, sponsored by, or in any way officially connected to Google LLC, YouTube, or YouTube Music. "YouTube" and "YouTube Music" are trademarks of Google LLC and are used here only to describe what this software interoperates with.

**No accounts, no API keys.** The player does not use the YouTube Data API and never signs you in. It resolves publicly available audio streams through yt-dlp, exactly as yt-dlp would on the command line.

**Nothing is downloaded or redistributed.** Audio is streamed for playback only — no media files are written to disk, and this repository contains no media content.

**You are responsible for your own use.** Accessing YouTube is subject to [YouTube's Terms of Service](https://www.youtube.com/t/terms) and to the copyright law of your jurisdiction. This project is published for personal, educational use; make sure the way you use it is permitted where you are.

**Provided as-is.** The software comes with no warranty of any kind, as stated in the [MIT License](LICENSE). If YouTube changes how streams are served, playback can stop working without notice.

---

## Acknowledgements

Built on [Textual](https://github.com/Textualize/textual), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [python-vlc](https://github.com/oaubert/python-vlc), [Peewee](https://github.com/coleifer/peewee), and [Click](https://github.com/pallets/click).

## License

MIT — see [LICENSE](LICENSE).
