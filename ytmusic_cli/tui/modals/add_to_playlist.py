"""Pick a playlist to receive the selected song."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from ytmusic_cli.music.types import Playlist
from ytmusic_cli.tui.widgets.select_list import SelectList


class AddToPlaylistModal(ModalScreen[int | None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        playlists: list[Playlist],
        title: str = "Add to playlist",
    ) -> None:
        super().__init__()
        self._playlists = playlists
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="picker_panel"):
            yield Static(self._title)
            if not self._playlists:
                yield Static("No playlists yet. Create one in Playlists.")
            else:
                yield SelectList(
                    *[
                        Option(item["name"], id=f"pl_{item['id']}")
                        for item in self._playlists
                    ],
                    id="playlist_picker",
                )

    def on_mount(self) -> None:
        if self._playlists:
            picker = self.query_one("#playlist_picker", SelectList)
            picker.highlighted = 0
            picker.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None or not option_id.startswith("pl_"):
            self.dismiss(None)
            return
        self.dismiss(int(option_id.removeprefix("pl_")))

    def action_cancel(self) -> None:
        self.dismiss(None)
