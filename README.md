# YTMusic CLI

A keyboard-driven, audio-only terminal music player for YouTube, built with Python, [Textual](https://github.com/Textualize/textual), [yt-dlp](https://github.com/yt-dlp/yt-dlp), and VLC.

Search YouTube, queue tracks, and keep local profiles and playlists — without leaving the terminal and without loading video.

> **Unofficial.** This is a personal hobby project and is not affiliated with, endorsed by, or sponsored by Google LLC, YouTube, or YouTube Music. Please read the [Disclaimer](#disclaimer) before using it.

---

## Features

- **Audio-only streaming**: resolves and plays the audio stream, so no bandwidth is spent on video.
- **Search-first TUI**: search is the landing mode; now-playing chrome stays visible in every mode.
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
- **[uv](https://docs.astral.sh/uv/)** (recommended) for dependency management

`python-vlc` is only a binding; playback fails without a system libVLC and a working audio device.

---

## Installation

```bash
git clone https://github.com/hakanayaz14159/ytmusic-cli.git
cd ytmusic-cli
uv sync
uv run ytmusic-cli
```

For the linters, type checker, and test dependencies:

```bash
uv sync --all-groups
```

---

## Usage

```bash
uv run ytmusic-cli            # launch the TUI
uv run ytmusic-cli --version
uv run ytmusic-cli --help
```

Press `?` in the app for the keymap: `1`–`5` switch modes and `/` jumps to the query field.

### Your data

Everything lives on your machine. Profiles, playlists, and the track metadata they reference are stored in a single SQLite file in the platform data directory (`~/.local/share/ytmusic-cli/ytmusic.db` on Linux). There is no account, no server, and no telemetry.

File logging is off by default. Enable it when you want to report a bug:

```bash
YTMUSIC_LOG=1 uv run ytmusic-cli   # writes a timestamped log next to the database
```

Logs redact query strings from stream URLs and the `Cookie` and `Authorization` headers, but skim a log before attaching it to an issue.

---

## Architecture

The project follows a hexagonal (ports and adapters) layout — the domain core does not import Textual, VLC, yt-dlp, or Peewee:

```
ytmusic_cli/
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

[`YoutubeDoc.md`](YoutubeDoc.md) explains how search, stream resolution, and the local stream proxy actually work, including why VLC is pointed at a localhost proxy. [`AGENTS.md`](AGENTS.md) is the engineering spec the codebase is held to.

---

## Development

```bash
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

Contributions follow test-first development, strict `mypy`, and Conventional Commits; the details are in [`AGENTS.md`](AGENTS.md).

---

## Project status

Alpha, and a personal project I maintain for my own listening. Bug reports and pull requests are welcome, but there is no roadmap, no release schedule, and no support commitment. Since playback depends on yt-dlp keeping up with YouTube, expect the occasional breakage and keep `yt-dlp` up to date (`uv lock --upgrade-package yt-dlp`).

---

## Disclaimer

**Not affiliated with Google.** YTMusic CLI is an independent, unofficial project. It is not affiliated with, endorsed by, sponsored by, or in any way officially connected to Google LLC, YouTube, or YouTube Music. "YouTube" and "YouTube Music" are trademarks of Google LLC and are used here only to describe what this software interoperates with.

**No accounts, no API keys.** The player does not use the YouTube Data API and never signs you in. It resolves publicly available audio streams through yt-dlp, exactly as yt-dlp would on the command line.

**Nothing is downloaded or redistributed.** Audio is streamed for playback only — no media files are written to disk, and this repository contains no media content.

**You are responsible for your own use.** Accessing YouTube is subject to [YouTube's Terms of Service](https://www.youtube.com/t/terms) and to the copyright law of your jurisdiction. This project is published for personal, educational use; make sure the way you use it is permitted where you are.

**Provided as-is.** The software comes with no warranty of any kind, as stated in the [MIT License](LICENSE). If YouTube changes how streams are served, playback can stop working without notice.

---

## Acknowledgements

Built on [Textual](https://github.com/Textualize/textual), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [python-vlc](https://github.com/oaubert/python-vlc), [Peewee](https://github.com/coleifer/peewee), and [Click](https://github.com/pallets/click).

## License

MIT — see [LICENSE](LICENSE).
