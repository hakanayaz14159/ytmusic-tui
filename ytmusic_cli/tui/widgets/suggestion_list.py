"""Query completion list for the search input."""

from textual.widgets import OptionList
from textual.widgets.option_list import Option


class SuggestionList(OptionList):
    can_focus = False

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            name=name, id=id, classes=classes, disabled=disabled, markup=False
        )
        self._queries: list[str] = []
        self.display = False

    def set_suggestions(self, queries: list[str]) -> None:
        self._queries = list(queries)
        self.clear_options()
        if queries:
            self.add_options([Option(query) for query in queries])
        self.highlight_at(None)
        self.display = bool(queries)

    def highlight_at(self, index: int | None) -> None:
        self.highlighted = index

    def highlighted_index(self) -> int | None:
        index = self.highlighted
        if isinstance(index, int):
            return index
        return None

    def selected_query(self) -> str | None:
        index = self.highlighted_index()
        if index is None or index >= len(self._queries):
            return None
        return self._queries[index]

    def highlight_next(self) -> str | None:
        current = self.highlighted_index()
        if self.option_count == 0:
            return None
        if current is None:
            self.highlight_at(0)
        elif current < self.option_count - 1:
            self.highlight_at(current + 1)
        return self.selected_query()

    def highlight_previous(self) -> str | None:
        current = self.highlighted_index()
        if current is None:
            return None
        if current <= 0:
            self.highlight_at(None)
            return None
        self.highlight_at(current - 1)
        return self.selected_query()
