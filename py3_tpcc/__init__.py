"""Python DBAPI 2.0 Compliance Test Suite"""

import logging
from typing import Final

from py3_tpcc.results import Results

__version__: Final[str] = "0.0.1"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

__all__ = ["Results"]
