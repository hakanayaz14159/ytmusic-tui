"""Search use cases."""

import logging

from ytmusic_tui.consts import DEFAULT_SUGGEST_LIMIT, MIN_SUGGEST_CHARS
from ytmusic_tui.exceptions import ValidationError
from ytmusic_tui.music.ports import MusicSourceProtocol
from ytmusic_tui.music.types import Song

logger = logging.getLogger(__name__)


class SearchService:
    """Delegates music search to a MusicSourceProtocol adapter."""

    def __init__(self, source: MusicSourceProtocol) -> None:
        self._source = source

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        if not query.strip():
            logger.warning("search rejected empty query")
            raise ValidationError("Search query must not be empty")
        return self._source.search(query, max_results=max_results)

    def suggest(
        self, query: str, max_results: int = DEFAULT_SUGGEST_LIMIT
    ) -> list[str]:
        cleaned = query.strip()
        if len(cleaned) < MIN_SUGGEST_CHARS:
            return []
        return self._source.suggest(cleaned, max_results=max_results)
