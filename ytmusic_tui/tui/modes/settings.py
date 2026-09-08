"""Settings mode: per-profile volume and search limit."""

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ytmusic_tui.consts import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_VOLUME,
    MAX_SEARCH_LIMIT,
    MAX_VOLUME,
    MIN_SEARCH_LIMIT,
)
from ytmusic_tui.exceptions import YTMusicError
from ytmusic_tui.music.types import UserSettings
from ytmusic_tui.tui.app import ytmusic_app
from ytmusic_tui.tui.widgets.select_list import SelectList

_VOLUME_STEP = 5
_LIMIT_STEP = 1


class SettingsMode(Vertical):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("s", "save", "Save", show=False),
        Binding("left", "adjust_down", show=False),
        Binding("right", "adjust_up", show=False),
        Binding("h", "adjust_down", show=False),
        Binding("l", "adjust_up", show=False),
    ]

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._settings: UserSettings = {
            "default_volume": DEFAULT_VOLUME,
            "search_limit": DEFAULT_SEARCH_LIMIT,
        }

    def compose(self) -> ComposeResult:
        yield SelectList(id="settings_list", markup=False)

    def reload(self) -> None:
        app = ytmusic_app(self.app)
        self._settings = app.settings_service.get()
        self._refresh_options()

    def activate(self) -> None:
        self.query_one("#settings_list", SelectList).focus()

    @work(thread=True, exclusive=True, group="settings")
    def action_save(self) -> None:
        app = ytmusic_app(self.app)
        try:
            saved = app.settings_service.save(self._settings)
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._on_saved, saved)

    def _on_saved(self, settings: UserSettings) -> None:
        self._settings = settings
        self.notify("Settings saved", severity="information")
        self._refresh_options()

    def action_adjust_up(self) -> None:
        self._adjust(1)

    def action_adjust_down(self) -> None:
        self._adjust(-1)

    def _adjust(self, direction: int) -> None:
        option_list = self.query_one("#settings_list", SelectList)
        index = option_list.highlighted
        if index == 0:
            volume = self._settings["default_volume"] + direction * _VOLUME_STEP
            self._settings["default_volume"] = max(0, min(MAX_VOLUME, volume))
        elif index == 1:
            limit = self._settings["search_limit"] + direction * _LIMIT_STEP
            self._settings["search_limit"] = max(
                MIN_SEARCH_LIMIT,
                min(MAX_SEARCH_LIMIT, limit),
            )
        self._refresh_options()

    def on_option_list_option_selected(
        self,
        _event: OptionList.OptionSelected,
    ) -> None:
        self.action_adjust_up()

    def _refresh_options(self) -> None:
        option_list = self.query_one("#settings_list", SelectList)
        highlighted = option_list.highlighted
        option_list.clear_options()
        option_list.add_option(
            Option(f"Default volume    {self._settings['default_volume']}%", id="vol")
        )
        option_list.add_option(
            Option(
                f"Search results    {self._settings['search_limit']}",
                id="limit",
            )
        )
        option_list.highlighted = 0 if highlighted is None else highlighted
