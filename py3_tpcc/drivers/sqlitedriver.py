from py3_tpcc.drivers.abstractdriver import AbstractDriver
from py3_tpcc.drivers.registry import register_driver


@register_driver("sqlite")
class SQLiteDriver(AbstractDriver):
    pass
