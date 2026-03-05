"""
Google Cloud Spanner TPC-C Database Driver

Implements the `AbstractDriver` interface for Google Cloud Spanner.
This provides the translation layer between the TPC-C executor operations
and the Google Cloud Spanner remote APIs.

NOTE: This is a placeholder implementation pending full transactional mapping.
"""

from py3_tpcc.drivers.abstractdriver import AbstractDriver
from py3_tpcc.drivers.registry import register_driver


@register_driver("spanner")
class SpannerDriver(AbstractDriver):
    """
    Concrete implementation of the Spanner database driver.
    Note: Currently a stub implementation.
    """

    def make_default_config(self):
        return {}
