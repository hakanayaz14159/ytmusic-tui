from textual.widgets import Static


class AccountSelection(Static):
    """An account selection widget."""

    def render(self) -> str:
        return "Account Selection"
