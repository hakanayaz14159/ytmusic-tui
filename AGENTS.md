# AGENTS.md — Unified Engineering Operating System for YTMusic CLI

This document is the authoritative engineering specification and operating manual for any agent or engineer contributing to `ytmusic-cli`. It defines a single cohesive development system combining architecture, test-driven development, static typing, terminal interface standards, and delivery discipline.

---

## 1. System Overview & Core Philosophy

**YTMusic CLI** is an unofficial, high-performance terminal client and TUI (Terminal User Interface) for YouTube Music built with **Python 3.11+**, **Textual**, **yt-dlp**, **python-vlc**, and **Peewee (SQLite)**.

Every contribution to this codebase is governed by five non-negotiable tenets:

1. **Test-Driven Development (TDD)**: No production code without a pre-existing failing test (Red-Green-Refactor).
2. **Hexagonal Architecture (Ports & Adapters)**: The domain core remains completely pure and isolated from external dependencies (YouTube network API, audio hardware, SQLite database).
3. **Strict Static Typing & Code Hygiene**: Zero untyped functions, zero `Any` shortcuts, zero inline imports, and full `mypy` strictness.
4. **Keyboard-First Terminal Ergonomics**: Intuitive, low-latency keyboard navigation with instant visual feedback and non-blocking background workers.
5. **Deterministic Execution**: Zero hard sleeps in tests, isolated in-memory test databases, and sub-second test execution.

---

## 2. Architecture & Domain Boundaries

The application follows an inward-pointing **Hexagonal (Ports & Adapters)** and **Domain-Driven** architecture:

```
+-------------------------------------------------------------+
| Presentation Layer: Textual TUI / Click CLI                 |
| (Screens, Widgets, Keybindings, TCSS Styling)               |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Application Layer: Workflows & Use Cases                    |
| (SearchService, PlaybackService, PlaylistService)           |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Ports: Abstract Protocol Contracts (typing.Protocol)        |
| (AudioPlayerProtocol, MusicSourceProtocol, Repository)      |
+------------------------------+------------------------------+
                               ^
                               | implements
+------------------------------+------------------------------+
| Infrastructure & Adapters Layer                             |
| - yt-dlp Adapter (YouTube metadata & stream extraction)     |
| - python-vlc Adapter (System audio engine)                  |
| - Peewee ORM (SQLite database persistence)                  |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Domain Layer: Pure Entities & Business Invariants           |
| (Song, Playlist, User, PlaybackState, Domain Errors)        |
+-------------------------------------------------------------+
```

### Architectural Invariants:

1. **Pure Domain (`ytmusic_cli.music.types`, domain models)**:
   - Contains core entities (`Song`, `Playlist`, `User`, `PlaybackState`) and business logic.
   - **ZERO external dependencies**: Must never import Textual, VLC, yt-dlp, or Peewee.
2. **Ports (Protocols)**:
   - Defined using `typing.Protocol` with `@runtime_checkable`.
   - Adapters must conform strictly to these contracts:
     ```python
     from typing import Protocol, runtime_checkable
     from ytmusic_cli.music.types import Song

     @runtime_checkable
     class AudioPlayerProtocol(Protocol):
         def play(self, url: str) -> None: ...
         def pause(self) -> None: ...
         def stop(self) -> None: ...
         def is_playing(self) -> bool: ...
         def set_volume(self, volume: int) -> None: ...
         def get_volume(self) -> int: ...

     @runtime_checkable
     class MusicSourceProtocol(Protocol):
         def search(self, query: str, max_results: int = 10) -> list[Song]: ...
         def get_stream_url(self, video_id: str) -> str: ...
     ```
3. **Unidirectional Reactive State Flow**:
   - `AppState` (singleton) contains reactive `AtomicData[T]` observables (`current_song`, `current_user`, `current_playlist`).
   - Widgets subscribe to state changes on mount and unsubscribe on unmount to prevent leaks.
   - UI actions invoke application services, which update state; state changes propagate reactively to UI widgets.
4. **Non-Blocking TUI Event Loop**:
   - Network requests (yt-dlp searches, stream resolution), audio player initialization, and database disk I/O **must never run on the main Textual event loop**.
   - Use Textual's `@work(thread=True)` worker decorator for background I/O.

---

## 3. Test-Driven Development (TDD) System

All development strictly adheres to the **Red-Green-Refactor** discipline.

### 1. The Red-Green-Refactor Cycle

- **RED (Write Failing Test First)**:
  - Write a focused test in `tests/test_<feature>.py` asserting the required contract or behavior.
  - Run `uv run pytest tests/test_<feature>.py -k <test_name>` and confirm it fails for the expected reason.
- **GREEN (Write Minimal Implementation)**:
  - Write the simplest, most direct code that makes the test pass.
  - Do not introduce speculative helpers, unused configuration, or premature generalizations.
  - Verify green: `uv run pytest`.
- **REFACTOR (Clean & Verify)**:
  - Clean up duplication, enforce typing, run formatting and linting.
  - Re-run all tests to guarantee zero regressions.

### 2. Testing Invariants & Constraints

- **Zero Hard Sleeps (Strictly Enforced)**:
  - NEVER use `time.sleep()` or `asyncio.sleep()` in test suites.
  - For Textual TUI tests, use `async with app.run_test() as pilot:` combined with `await pilot.pause()` or condition polling.
- **Complete Test Isolation**:
  - Database tests must use the `test_db` fixture (`SqliteDatabase(":memory:")`). Tests must never write to real filesystem databases.
  - YouTube network requests are mocked via `mock_youtube`. The automated test suite runs 100% offline.
  - Audio playback is mocked via `mock_player`. Tests run silently with zero audio hardware dependencies.
  - Shared state in `AppState` must be reset between tests via `AppState().reset()`.
- **Test Pyramid & Speed**:
  - Unit tests (<10ms per test): Domain logic, data conversions, and service workflows.
  - Integration tests (<50ms per test): Database queries and repository interactions with in-memory SQLite.
  - TUI Pilot tests (<200ms per test): Screen mount lifecycle, widget interactions, and keybindings.
  - Full test suite execution target: <2.0 seconds.

---

## 4. Typing, Linting & Code Discipline

Target runtime: **Python 3.11+**.

### 1. Imports & Module Hygiene

- **No Inline Imports**: All imports must reside at the very top of the module file. Never import inside functions, methods, or conditionals.
- Grouping: Standard library -> Third-party -> Local application modules, separated by single blank lines (Ruff `I` rules).
- For type-checking circularity only:
  ```python
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from ytmusic_cli.main import YTMusicApp
  ```

### 2. Static Typing Standards

- Full `mypy` strict compliance (`disallow_untyped_defs = true`, `strict_equality = true`).
- Every function, method, and `__init__` must have explicit argument types and return type annotations (`-> None`, `-> int`, etc.).
- `Any` is an anti-pattern. Untyped external dictionaries from yt-dlp must be cast or validated into domain `TypedDict` or dataclasses immediately at adapter boundaries.
- Python 3.11+ idioms:
  - Use native union syntax `A | B` and `T | None` (no `Union` or `Optional`).
  - Use `collections.abc` for generic containers (`Callable`, `Sequence`, `Generator`, `Mapping`).
  - Use `typing.Self` for methods returning `self`.

### 3. Error Handling Hierarchy

- Never raise bare `Exception` or catch bare `except:`.
- All custom exceptions inherit from `YTMusicError`:
  - `PlaybackError`: Audio output or VLC player failure.
  - `StreamExtractionError`: Inability to resolve stream URLs from YouTube.
  - `TrackNotFoundError`: Requested song or video ID not found.
  - `DatabaseError`: Persistence or relational constraint failure.
- When wrapping third-party errors, preserve traceback context: `raise StreamExtractionError(...) from err`.

---

## 5. Terminal User Interface (TUI) System

The TUI is implemented with **Textual** and provides a keyboard-first, responsive terminal experience.

### 1. Three-Zone Visual Layout

```
+-------------------------------------------------------------+
| Header Zone: [App Title]            [Active Profile / State]|
+-------------------------------------------------------------+
| Screen Content Area (Dynamic):                              |
|   - MainMenuScreen                                          |
|   - SearchScreen (Query input + Results table)              |
|   - PlaylistScreen (User playlists + Track listing)         |
|   - SettingsScreen / HelpModal                              |
+-------------------------------------------------------------+
| Mini-Player Zone (Persistent):                              |
|   ▶ Track Title - Artist [01:45/03:30] [Vol: 80%] [==----]  |
+-------------------------------------------------------------+
| Footer Zone: [q] Quit  [Space] Play/Pause  [/] Search  [?]  |
+-------------------------------------------------------------+
```

### 2. Keyboard Navigation Ergonomics

- `Space`: Toggle playback (Play / Pause).
- `j` / `k` or `Down` / `Up`: Navigate options, search results, and playlist rows.
- `Enter`: Select / Play item / Open subscreen.
- `/`: Quick focus on search bar.
- `+` / `-`: Volume up / down in 5% increments.
- `h` or `?`: Toggle help overlay.
- `q` or `Esc`: Back to previous screen / cancel input / quit application.

### 3. Theme & Styling System (`ytmusic_theme`)

- Background: `#0F0F0F` (Dark terminal canvas).
- Surface / Panels: `#1A1A1A` and `#222222`.
- Primary Accent: `#FF0000` (YouTube Brand Red).
- Secondary Accent: `#3EA6FF` (Focus indicators and active links).
- Text Primary: `#FFFFFF`.
- Text Muted: `#888888`.
- Status Playing / Success: `#2BA640`.
- All interactive widgets must define explicit `:focus` visual styling in `app.tcss`.
- Progress formatting: Standardized `MM:SS` duration display and Unicode volume gauges `[▮▮▮▯▯]`.
- Responsive breakpoint: Minimum terminal size 80x24; collapsible ASCII art banner when terminal height < 30 rows.

---

## 6. Work Breakdown & Definition of Done

### 1. Task Sizing & Specification

- Features must be broken down into **atomic 30–60 minute tasks**.
- Every task specification must use the **Given / When / Then** format:
  ```markdown
  ### [ ] Task: [Clear Descriptive Name]

  **Description**: [Single responsibility of this task]

  **Acceptance Criteria**:

  - **Given**: [Pre-condition or state]
  - **When**: [Action taken]
  - **Then**: [Verifiable result]

  **Files to Touch**:

  - `ytmusic_cli/...`
  - `tests/test_...`
  ```

### 2. Definition of Done (DoD) Checklist

No task is considered complete until all items pass:

- [ ] **TDD Verified**: Failing test written first (Red) and now passing (Green).
- [ ] **Tests Pass**: `uv run pytest` passes 100% with no skipped or flaky tests.
- [ ] **Zero Sleeps**: No `time.sleep` or `asyncio.sleep` anywhere in test code.
- [ ] **Type Check Clean**: `uv run mypy ytmusic_cli/ tests/` reports 0 errors.
- [ ] **Linter Clean**: `uv run ruff check ytmusic_cli/ tests/` reports 0 warnings.
- [ ] **Format Clean**: `uv run ruff format --check ytmusic_cli/ tests/` passes.
- [ ] **Surgical Scope**: Diffs contain only changes strictly required for the task.

---

## 7. Agent Execution Playbook

When an agent is assigned a task, it must execute this exact workflow:

```
[1. Read Spec & Rules]
        |
        v
[2. Formulate Acceptance Criteria (Given/When/Then)]
        |
        v
[3. Write Failing Test in tests/ (Red)]
        |
        v
[4. Run pytest to Confirm Expected Failure]
        |
        v
[5. Write Minimal Production Code in ytmusic_cli/ (Green)]
        |
        v
[6. Run pytest to Confirm Green]
        |
        v
[7. Refactor Code, Add Type Annotations, Check Top Imports]
        |
        v
[8. Run Full Verification Suite (Ruff + Mypy + Pytest)]
        |
        v
[9. Verify Definition of Done Checklist]
```

---

## 8. Directory Layout & Command Reference

### Directory Map

```
ytmusic-cli/
├── .cursor/
│   └── rules/
│       ├── architecture-domain.mdc     # Hexagonal architecture & state rules
│       ├── project-management.mdc      # Task breakdown & DoD
│       ├── python-typing-linting.mdc   # Strict typing & ruff standards
│       ├── tdd-workflow.mdc            # TDD Red-Green-Refactor & zero sleeps
│       └── tui-ux-design.mdc           # Textual TUI design & keyboard UX
├── docs/                               # Architectural documentation & ADRs
├── tests/
│   ├── conftest.py                     # Shared fixtures (test_db, mock_youtube, mock_player)
│   ├── test_setup.py                   # Baseline verification tests
│   └── ...                             # Feature test modules
├── ytmusic_cli/
│   ├── consts.py                       # Paths, database constants, app metadata
│   ├── main.py                         # Click CLI entrypoint & YTMusicApp
│   ├── theme.py                        # Custom Textual theme definitions
│   ├── app.tcss                        # Global Textual CSS styling
│   ├── db/                             # Peewee models and database setup
│   ├── music/                          # AppState, domain types, yt-dlp adapter
│   ├── tui/                            # Textual screens, widgets, headers, footers
│   └── utils/                          # Common helpers (singleton, etc.)
├── pyproject.toml                      # Project metadata & tool configs
└── Makefile                            # Development command targets
```

### Essential Commands

| Command                                        | Action                                           |
| ---------------------------------------------- | ------------------------------------------------ |
| `uv sync --all-groups`                         | Install all runtime and development dependencies |
| `uv run pytest`                                | Run the full automated test suite                |
| `uv run pytest -k <name>`                      | Run specific tests matching a keyword            |
| `uv run pytest --cov=ytmusic_cli`              | Run tests with coverage reporting                |
| `uv run mypy ytmusic_cli/ tests/`              | Run strict static type checking                  |
| `uv run ruff check --fix ytmusic_cli/ tests/`  | Run Ruff linter with auto-fixing                 |
| `uv run ruff format ytmusic_cli/ tests/`       | Auto-format all Python code                      |
| `make lint`                                    | Run format check, linter, and mypy in one pass   |
| `uv run ytmusic-cli`                           | Launch the CLI application                       |
| `uv run textual run --dev ytmusic_cli/main.py` | Launch TUI in Textual dev/debug mode             |
