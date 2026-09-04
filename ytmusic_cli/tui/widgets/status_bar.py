"""Context-sensitive key hint strip."""

from textual.widgets import Static


class StatusBar(Static):
    """Single-line hints for the active mode."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__("", name=name, id=id, classes=classes, disabled=disabled)

    def set_hints(self, hints: str) -> None:
        self.update(hints)
