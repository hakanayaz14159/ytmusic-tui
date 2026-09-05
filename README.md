# YTMusic CLI

A modern, audio-only Terminal User Interface (TUI) music player for YouTube, built with Python, [Textual](https://github.com/Textualize/textual), and [yt-dlp](https://github.com/yt-dlp/yt-dlp).

YTMusic CLI allows you to stream audio directly from YouTube without video overhead, manage multiple profiles, organize playlists, search tracks, and download audio locally for offline listening—all within a rich terminal interface.

---

## Features

- **Audio-Only Streaming**: Low-bandwidth, high-quality audio streaming from YouTube without downloading video.
- **Interactive TUI**: Built on modern Textual with intuitive navigation, dark theme, and visual playback controls.
- **Profile Management**: Support for multiple user profiles with independent preferences and playlists.
- **Custom Playlists**: Create, edit, and organize custom playlists backed by a local SQLite database.
- **Search & Discovery**: Fast keyword search for songs, albums, and artists.
- **Offline Downloads**: Download audio tracks locally with embedded metadata for offline playback.
- **Test-Driven Architecture**: Designed from the ground up with strict separation of concerns, comprehensive test coverage, and isolated in-memory test databases.

---

## Requirements

- **Python**: 3.11 or higher
- **Package Manager**: [uv](https://docs.astral.sh/uv/) (recommended)
- **Audio Backend**: System `libvlc` (`vlc` package on Linux / macOS / Windows)

---

## Installation & Setup

### Using `uv` (Recommended)

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/ytmusic-cli.git
   cd ytmusic-cli
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Run the application:
   ```bash
   uv run ytmusic-cli
   ```

### Development Installation

To install all development tools, linters, and testing dependencies:

```bash
uv sync --all-groups
```

---

## Usage

### Launch the TUI

```bash
uv run ytmusic-cli
```

### Command Line Options

```bash
# Show version
uv run ytmusic-cli --version

# Show help
uv run ytmusic-cli --help
```

### Key Bindings

| Key             | Action                                             |
| --------------- | -------------------------------------------------- |
| `/`             | Search and focus the query field                   |
| `1`–`5`         | Search / Queue / Playlists / Profiles / Settings   |
| `Tab`           | Next mode                                          |
| `Shift+Tab`     | Previous mode                                      |
| `Space`         | Play / pause                                       |
| `+` / `=` / `-` | Volume up / down                                   |
| `>` / `<`       | Next / previous in queue                           |
| `j` / `k`       | Move in lists                                      |
| `Enter`         | Play the highlighted track                         |
| `a`             | Append highlighted track to the queue              |
| `A`             | Add highlighted or now-playing track to a playlist |
| `d`             | Remove from queue or playlist                      |
| `n`             | New playlist or profile; save queue as playlist    |
| `o`             | Open a playlist into the queue (Queue mode)        |
| `w`             | Overwrite the working playlist from the queue      |
| `s`             | Save settings                                      |
| `?`             | Help                                               |
| `Esc`           | Blur search / close a dialog                       |
| `q`             | Quit (when not typing)                             |
| `Ctrl+q`        | Quit                                               |

---

## Architecture & Design

The project follows a clean layered architecture with strict separation of concerns:

```
ytmusic_cli/
├── db/             # Data access layer (Peewee SQLite models & migrations)
│   ├── user.py     # Profile & user account entities
│   ├── playlist.py # Playlists & track associations
│   └── song.py     # Track metadata persistence
├── music/          # Domain & infrastructure services
│   ├── types.py    # Domain models and TypedDicts
│   ├── youtube.py  # yt-dlp adapter for search, extraction, and downloads
│   └── state.py    # Reactive application state
├── tui/            # Presentation layer (Textual shell, modes, widgets)
│   ├── shell.py    # Persistent chrome: modes, now-playing, status
│   ├── modes/      # Search, Queue, Playlists, Profiles, Settings
│   ├── widgets/    # Mode bar, song table, now playing
│   └── modals/     # Help, prompts, confirmations
└── main.py         # Application entry point and CLI commands
```

### Test-Driven Design (TDD)

Every feature is developed test-first:

1. **Domain & Data**: Tested with isolated in-memory SQLite fixtures (`:memory:` via `test_db`).
2. **YouTube Adapter**: Tested using `mock_youtube` to eliminate flaky network calls during tests.
3. **Audio Playback**: Tested using `mock_player` for silent, deterministic headless verification.
4. **TUI Screens**: Tested asynchronously using Textual's test pilot (`app.run_test()`).

---

## Development & Quality Assurance

All development commands are powered by `uv` and simplified with `make`:

```bash
# Run unit and integration tests
make test
# or: uv run pytest

# Run tests with coverage report
make test-cov
# or: uv run pytest --cov=ytmusic_cli --cov-report=term

# Lint and check formatting
make lint
# or: uv run ruff check ytmusic_cli/ tests/ && uv run mypy ytmusic_cli/

# Automatically format code
make format
# or: uv run ruff format ytmusic_cli/ tests/ && uv run ruff check --fix ytmusic_cli/ tests/

# Run Textual dev server / live console
make dev
# or: uv run textual run --dev ytmusic_cli/main.py
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
