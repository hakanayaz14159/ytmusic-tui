"""Top mode tabs and active profile name."""

from collections.abc import Callable  # noqa: TC003

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import User

MODE_LABELS: tuple[tuple[str, str], ...] = (
    ("search", "Search"),
    ("queue", "Queue"),
    ("playlists", "Playlists"),
    ("profiles", "Profiles"),
    ("settings", "Settings"),
)


class ModeBar(Horizontal):
    """Mode tabs with the active profile on the right."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._active = "search"
        self._unsub_user: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        for mode_id, label in MODE_LABELS:
            yield Static(label, id=f"tab_{mode_id}", classes="mode-tab")
        yield Static("", id="mode_user")

    def on_mount(self) -> None:
        state = AppState()
        self._unsub_user = state.current_user.subscribe(self._on_user)
        self.set_active(self._active)
        self._on_user(state.current_user.get())

    def on_unmount(self) -> None:
        if self._unsub_user is not None:
            self._unsub_user()
            self._unsub_user = None

    def set_active(self, mode_id: str) -> None:
        self._active = mode_id
        if not self.is_mounted:
            return
        for tab_id, _label in MODE_LABELS:
            tab = self.query_one(f"#tab_{tab_id}", Static)
            tab.set_class(tab_id == mode_id, "-active")

    def _on_user(self, user: User | None) -> None:
        if not self.is_mounted:
            return
        name = user["username"] if user is not None else ""
        self.query_one("#mode_user", Static).update(name)
