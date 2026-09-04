from pathlib import Path

import platformdirs

APP_NAME = "ytmusic-cli"
DB_NAME = "ytmusic.db"
DEVELOPER = "arandomdev"

DEFAULT_USERNAME = "local"
DEFAULT_VOLUME = 80
MAX_VOLUME = 100
DEFAULT_SEARCH_LIMIT = 10
MIN_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 25
WIDE_LAYOUT_COLUMNS = 110
COMPACT_HEIGHT_ROWS = 24
PLAYBACK_STALL_TICKS = 15

APP_DIR = Path(platformdirs.user_data_dir(APP_NAME, DEVELOPER))
DB_PATH = APP_DIR.joinpath(DB_NAME)

if not APP_DIR.exists():
    APP_DIR.mkdir(parents=True, exist_ok=True)

if not DB_PATH.exists():
    DB_PATH.touch()
