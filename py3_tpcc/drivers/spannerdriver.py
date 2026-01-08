from py3_tpcc.drivers.abstractdriver import AbstractDriver
from py3_tpcc.drivers.registry import register_driver


@register_driver("spanner")
class SpannerDriver(AbstractDriver):

    def make_default_config(self):
        return {}
