"""Main entry point for YTMusic TUI application."""

import logging
import sys

import click

from ytmusic_tui import __version__
from ytmusic_tui.db.bootstrap import bootstrap
from ytmusic_tui.db.repositories import (
    AppConfigRepository,
    PlaylistRepository,
    SongRepository,
    UserRepository,
)
from ytmusic_tui.exceptions import VLCUnavailableError
from ytmusic_tui.music.player import VLCPlayer
from ytmusic_tui.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
    SettingsService,
)
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.youtube import Youtube
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.utils.log import configure_logging

logger = logging.getLogger(__name__)


def build_production_app() -> YTMusicApp:
    state = AppState()
    source = Youtube()
    player = VLCPlayer()
    users = UserRepository()
    account_service = AccountService(users, state, AppConfigRepository())
    account_service.ensure_default_user()
    return YTMusicApp(
        search_service=SearchService(source),
        playback_service=PlaybackService(player, source, state),
        account_service=account_service,
        playlist_service=PlaylistService(PlaylistRepository(SongRepository()), state),
        settings_service=SettingsService(users, state),
    )


@click.command()
@click.version_option(version=__version__)
def main() -> None:
    """YTMusic TUI — a terminal music player for YouTube audio.

    Unofficial project. Not affiliated with or endorsed by Google or YouTube.
    """

    try:
        log_path = configure_logging()
        if log_path is not None:
            logger.info("logging to %s", log_path)
        logger.info("starting ytmusic-tui")
        bootstrap()
        app = build_production_app()
        app.run()
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")
        sys.exit(0)
    except VLCUnavailableError as err:
        click.echo(str(err), err=True)
        sys.exit(1)
    except Exception as e:
        logger.exception("fatal error")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
