import os

from py3_tpcc.drivers.abstractdriver import AbstractDriver
from py3_tpcc.drivers.registry import register_driver


@register_driver("sqlite")
class SQLiteDriver(AbstractDriver):

    CONFIG_FILE = "sqlite.toml"

    def make_default_config(self):
        config_path = os.path.join(
            os.path.dirname(__file__), SQLiteDriver.CONFIG_FILE
        )
        self.load_config(config_path)
        return self.config
