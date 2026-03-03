#!/usr/bin/env python
# -----------------------------------------------------------------------
# Copyright (C) 2011
# Andy Pavlo
# http://www.cs.brown.edu/~pavlo/
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# -----------------------------------------------------------------------

import abc
from datetime import datetime
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from py3_tpcc import constants

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

    def __init__(self, name: str, ddl: str):
        self.name = name
        self.driver_name = f"{self.name.title()}Driver"
        self.ddl = ddl
        self.config: Dict[str, Any] = {}

    @abc.abstractmethod
    def make_default_config(self) -> Dict[str, Any]:
        """Generate the default configuration for this driver."""
        pass

    def load_config(self, config: Any) -> Optional[Dict[str, Any]]:
        if isinstance(config, dict):
            self.config.update(config)
            return self.config

        filename = str(config)
        if not os.path.isfile(filename):
            logging.error(f"Config file '{filename}' does not exist")
            return None

        with open(filename, "rb") as f:
            loaded = toml.load(f)
            if loaded:
                self.config.update(loaded)
            return self.config

    def format_config(self, config: Dict[str, Any]) -> str:
        # Add a header comment manually
        # since TOML writers usually don't support comments well
        header = (
            f"# {self.driver_name} Configuration File\n"
            f"# Created {datetime.now()}\n\n"
        )
        return header + tomli_w.dumps(config)

    def load_start(self) -> None:
        """Optional callback to indicate to the driver that
        the data loading phase is about to begin."""
        pass

    def load_end(self) -> None:
        """Optional callback to indicate to the driver that
        the data loading phase is finished."""
        pass

    def execute_start(self) -> None:
        """Optional callback before the execution phase starts"""
        pass

    def execute_end(self) -> None:
        """Callback after the execution phase finishes"""
        pass

    def load_item_end(self) -> None:
        """Optional callback to indicate to the driver that
        the ITEM data has been passed to the driver."""
        pass

    def load_warehouse_end(self, w_id: int) -> None:
        """Optional callback to indicate to the driver that
        the data for the given warehouse is finished."""
        pass

    def load_district_end(self, w_id: int, d_id: int) -> None:
        """Optional callback to indicate to the driver that
        the data for the given district is finished."""
        pass

    @abc.abstractmethod
    def load_tuples(self, table_name: str, tuples: List[Any]) -> None:
        """Load a list of tuples into the target table"""
        pass

    def execute_transaction(self, txn: str, params: Dict[str, Any]) -> Any:
        """Execute a transaction based on the given name"""

        if constants.TransactionTypes.DELIVERY == txn:
            result = self.do_delivery(params)
        elif constants.TransactionTypes.NEW_ORDER == txn:
            result = self.do_new_order(params)
        elif constants.TransactionTypes.ORDER_STATUS == txn:
            result = self.do_order_status(params)
        elif constants.TransactionTypes.PAYMENT == txn:
            result = self.do_payment(params)
        elif constants.TransactionTypes.STOCK_LEVEL == txn:
            result = self.do_stock_level(params)
        else:
            assert False, f"Unexpected TransactionType: {txn}"
        return (result, 0)

    @abc.abstractmethod
    def do_delivery(self, params: Dict[str, Any]) -> Any:
        """Execute DELIVERY Transaction
        Parameters Dict:
            w_id
            o_carrier_id
            ol_delivery_d
        """
        pass

    @abc.abstractmethod
    def do_new_order(self, params: Dict[str, Any]) -> Any:
        """Execute NEW_ORDER Transaction
        Parameters Dict:
            w_id
            d_id
            c_id
            o_entry_d
            i_ids
            i_w_ids
            i_qtys
        """
        pass

    @abc.abstractmethod
    def do_order_status(self, params: Dict[str, Any]) -> Any:
        """Execute ORDER_STATUS Transaction
        Parameters Dict:
            w_id
            d_id
            c_id
            c_last
        """
        pass

    @abc.abstractmethod
    def do_payment(self, params: Dict[str, Any]) -> Any:
        """Execute PAYMENT Transaction
        Parameters Dict:
            w_id
            d_id
            h_amount
            c_w_id
            c_d_id
            c_id
            c_last
            h_date
        """
        pass

    @abc.abstractmethod
    def do_stock_level(self, params: Dict[str, Any]) -> Any:
        """Execute STOCK_LEVEL Transaction
        Parameters Dict:
            w_id
            d_id
            threshold
        """
        pass
