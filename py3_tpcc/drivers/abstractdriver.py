import abc
from datetime import datetime
import logging
import os
import sys

try:
    if sys.version_info < (3, 11):
        import tomli as toml
    else:
        import tomllib as toml
except ImportError:
    # Fallback if tomli is not installed on older python
    import tomli as toml

import tomli_w


class AbstractDriver(abc.ABC):

    def __init__(self, name, ddl):
        self.name = name
        self.driver_name = "%sDriver" % self.name.title()
        self.ddl = ddl
        self.config = {}

    def make_default_config(self):
        raise NotImplementedError(
            "%s does not implement makeDefaultConfig" % (self.driver_name)
        )

    def load_config(self, filename):
        if not os.path.isfile(filename):
            logging.error(f"Config file '{filename}' does not exist")
            return None

        with open(filename, "rb") as f:
            loaded = toml.load(f)
            if loaded:
                self.config.update(loaded)
            return self.config

    def format_config(self, config):
        # Add a header comment manually
        # since TOML writers usually don't support comments well
        header = (
            f"# {self.driver_name} Configuration File\n"
            f"# Created {datetime.now()}\n\n"
        )
        return header + tomli_w.dumps(config)
