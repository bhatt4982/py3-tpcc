"""Python DBAPI 2.0 Compliance Test Suite"""

import logging
from typing import Final

__version__: Final[str] = "0.0.1"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__all__ = []
