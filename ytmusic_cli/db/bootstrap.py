from .db import db
from .playlist import Playlist
from .song import Song
from .user import User


def bootstrap() -> None:
    db.connect()
    db.create_tables([User, Song, Playlist])
    db.close()


bootstrap()
