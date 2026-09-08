from peewee import BooleanField, IntegerField

from ytmusic_tui.db.db import BaseModel


class AppConfig(BaseModel):
    skip_welcome = BooleanField(null=False, default=False)
    default_user_id = IntegerField(null=True)
