from pathlib import Path

import platformdirs

APP_NAME = "ytmusic-cli"
DB_NAME = "ytmusic.db"
DEVELOPER = "arandomdev"

APP_DIR = Path(platformdirs.user_data_dir(APP_NAME, DEVELOPER))
DB_PATH = APP_DIR.joinpath(DB_NAME)

if not APP_DIR.exists():
    APP_DIR.mkdir(parents=True, exist_ok=True)

if not DB_PATH.exists():
    DB_PATH.touch()
