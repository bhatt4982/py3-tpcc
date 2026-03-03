#!/usr/bin/env python
# -----------------------------------------------------------------------
# Copyright (C) 2011
# Andy Pavlo
# http:##www.cs.brown.edu/~pavlo/
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

    def __init__(self, name, ddl):
        self.name = name
        self.driver_name = "%sDriver" % self.name.title()
        self.ddl = ddl
        self.config = {}

    def make_default_config(self):
        raise NotImplementedError(
            "%s does not implement make_default_config" % (self.driver_name)
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

    def load_start(self):
        """Optional callback to indicate to the driver that
        the data loading phase is about to begin."""
        return None

    def load_end(self):
        """Optional callback to indicate to the driver that
        the data loading phase is finished."""
        return None

    def execute_start(self):
        """Optional callback before the execution phase starts"""
        return None

    def execute_end(self):
        """Callback after the execution phase finishes"""
        return None

    def load_item_end(self):
        """Optional callback to indicate to the driver that
        the ITEM data has been passed to the driver."""
        return None

    def load_warehouse_end(self, w_id):
        """Optional callback to indicate to the driver that
        the data for the given warehouse is finished."""
        return None

    def load_district_end(self, w_id, d_id):
        """Optional callback to indicate to the driver that
        the data for the given district is finished."""
        return None

    def load_tuples(self, table_name, tuples):
        """Load a list of tuples into the target table"""
        raise NotImplementedError(
            "%s does not implement load_tuples" % (self.driver_name)
        )
        return None

    def execute_transaction(self, txn, params):
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
            assert False, "Unexpected TransactionType: " + txn
        return result

    def do_delivery(self, params):
        """Execute DELIVERY Transaction
        Parameters Dict:
            w_id
            o_carrier_id
            ol_delivery_d
        """
        raise NotImplementedError(
            "%s does not implement do_delivery" % (self.driver_name)
        )

    def do_new_order(self, params):
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
        raise NotImplementedError(
            "%s does not implement do_new_order" % (self.driver_name)
        )

    def do_order_status(self, params):
        """Execute ORDER_STATUS Transaction
        Parameters Dict:
            w_id
            d_id
            c_id
            c_last
        """
        raise NotImplementedError(
            "%s does not implement do_order_status" % (self.driver_name)
        )

    def do_payment(self, params):
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
        raise NotImplementedError(
            "%s does not implement do_payment" % (self.driver_name)
        )

    def do_stock_level(self, params):
        """Execute STOCK_LEVEL Transaction
        Parameters Dict:
            w_id
            d_id
            threshold
        """
        raise NotImplementedError(
            "%s does not implement do_stock_level" % (self.driver_name)
        )
