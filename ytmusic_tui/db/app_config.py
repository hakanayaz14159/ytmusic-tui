from peewee import BooleanField, CharField, IntegerField

from ytmusic_tui.db.db import BaseModel
from ytmusic_tui.music.types import SkipKeymapMode


class AppConfig(BaseModel):
    skip_welcome = BooleanField(null=False, default=False)
    default_user_id = IntegerField(null=True)
    skip_keymap = CharField(max_length=8, null=False, default=SkipKeymapMode.AUTO)
