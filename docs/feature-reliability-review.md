# Feature reliability review

This audit covers the existing Search, Queue, Playlists, Profiles, and Settings modes, their playback/storage adapters, and the documented keyboard controls. Each implementation change has a regression that was observed failing before its fix.

## Completed tasks

### [x] Task: Preserve search intent across background requests

**Description**: Keep results, suggestions, errors, and focus aligned with the user's latest action.

**Acceptance Criteria**:

- **Given** overlapping searches or dismissed suggestions, **When** an older request completes, **Then** it cannot overwrite newer results or reopen dismissed suggestions.
- **Given** keyboard completion at the end of the suggestion list, **When** the user types again, **Then** the edit is processed normally.
- **Given** the user is editing the next query, **When** an earlier search completes, **Then** query focus is preserved.

**Files to Touch**: `tui/modes/search.py`, `tests/test_search_mode.py`.

### [x] Task: Make playback and queue transitions consistent

**Description**: Keep audio, queue position, and the displayed song synchronized.

**Acceptance Criteria**:

- **Given** repeated queue entries, **When** a specific occurrence is played, **Then** the queue retains that occurrence's position.
- **Given** the final track or a removed current track, **When** playback ends or the queue action completes, **Then** audio stops and the state reflects it.
- **Given** pending stream resolution or engine startup, **When** the request is superseded, removed, or skipped, **Then** it cannot start or retain obsolete audio.
- **Given** stream startup or proxy shutdown, **When** blocking engine/server work runs, **Then** it runs outside the UI event loop.
- **Given** engine startup fails or the app exits, **When** cleanup completes, **Then** audio resources stop and stale playing state is cleared.

**Files to Touch**: `main.py`, `music/services.py`, `music/stream_proxy.py`, `tui/shell.py`, `tests/test_app_reliability.py`, `tests/test_playback_queue.py`, `tests/test_player.py`, `tests/test_stream_proxy.py`.

### [x] Task: Protect saved playlists and profile state

**Description**: Make persistence failures and asynchronous profile changes safe for existing library contents.

**Acceptance Criteria**:

- **Given** a playlist or profile with saved memberships, **When** it is deleted, **Then** its membership rows are also removed and cannot reappear under a reused ID.
- **Given** an existing playlist, **When** replacement fails or a duplicate addition is rejected, **Then** the original songs and metadata remain intact.
- **Given** a working playlist, **When** it changes or its profile changes, **Then** working state refreshes or clears appropriately.
- **Given** in-flight load/save operations for a previous profile, **When** they complete after a profile switch, **Then** they preserve the current profile's queue and working selection.
- **Given** a confirmation dialog, **When** underlying selection changes, **Then** confirmation still refers to the displayed target and queue snapshot.
- **Given** visible playlist tracks, **When** a song is added, **Then** the display refreshes immediately.
- **Given** storage failures or an empty playlist, **When** the user invokes the action, **Then** the app reports the problem without crashing or replacing the queue.

**Files to Touch**: `db/repositories.py`, `music/services.py`, `main.py`, `tui/modes/playlists.py`, `tui/modes/profiles.py`, `tests/test_accounts.py`, `tests/test_playlists.py`, `tests/test_settings.py`.

### [x] Task: Complete keyboard navigation and literal text rendering

**Description**: Keep dialogs usable and show music/profile text faithfully.

**Acceptance Criteria**:

- **Given** an open dialog, **When** Tab or Ctrl+Q is pressed, **Then** Tab remains in the dialog and Ctrl+Q exits the app.
- **Given** Playlists mode, **When** Right/l or Left/h is pressed, **Then** focus moves between playlist names and tracks.
- **Given** a small terminal, **When** help is opened, **Then** its complete shortcut list is reachable by scrolling.
- **Given** bracketed titles, suggestions, or profile/playlist names, **When** they are rendered, **Then** the brackets remain literal text.

**Files to Touch**: `main.py`, `app.tcss`, `tui/shell.py`, `tui/modals/help.py`, `tui/modes/queue.py`, `tui/modes/playlists.py`, `tui/widgets/`, `tests/test_app_reliability.py`, `tests/test_help_modal.py`, `tests/test_now_playing.py`, `tests/test_search_mode.py`.

### [x] Task: Resolve usable audio streams and document actual capabilities

**Description**: Correct adapter fallback selection and remove unsupported feature claims.

**Acceptance Criteria**:

- **Given** yt-dlp-ranked formats and inherited headers, **When** fallback extraction runs, **Then** it prefers the best audio-only format and retains the required headers.
- **Given** incomplete metadata, **When** a search entry is converted, **Then** usable entries receive safe duration/uploader defaults.
- **Given** no explicit client override, **When** yt-dlp runs, **Then** it pins the android player client so stream URLs accept VLC's Range requests.
- **Given** an advertised feature with no implementation, **When** documentation is read, **Then** it is identified as future work.

**Files to Touch**: `music/youtube.py`, `tests/test_youtube_errors.py`, `README.md`, `YoutubeDoc.md`.

## Verification and limits

Run `uv run pytest`, `uv run mypy ytmusic_tui/ tests/`, `uv run ruff check ytmusic_tui/ tests/`, and `uv run ruff format --check ytmusic_tui/ tests/`. New concurrency tests coordinate using events; no hard sleeps were added. Database tests use the in-memory fixture and audio adapters are mocked.

The original baseline passed 230 offline tests but omitted these failure cases. Final verification passed 305 offline tests in 39.76 seconds, with the three opt-in network tests deselected. Mypy, Ruff lint, Ruff formatting, and whitespace checks passed. This runtime exceeds the aspirational two-second target in `AGENTS.md`.

The three opt-in live checks passed during this audit: YouTube search, suggestions, and stream access with returned headers. Run them with `uv run pytest tests/test_youtube_contract.py -m network`. Audio-device output still requires a manual listening check on a machine with libVLC. Offline downloads, local-file playback, seeking, embedded metadata, and YouTube library/account synchronization remain unimplemented and are explicitly identified in the documentation.
