from peewee import ForeignKeyField, ManyToManyField, TextField

from ytmusic_cli.db.db import BaseModel
from ytmusic_cli.db.song import Song
from ytmusic_cli.db.user import User


class Playlist(BaseModel):
    name = TextField(null=False)
    user = ForeignKeyField(User, backref="playlists", on_delete="CASCADE")
    songs = ManyToManyField(Song, backref="playlists", on_delete="CASCADE")
