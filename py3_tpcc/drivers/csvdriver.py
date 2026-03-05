# -*- coding: utf-8 -*-
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

"""
CSV TPC-C Database Driver

Implements the `AbstractDriver` interface to output TPC-C data and transaction
logs to CSV files. Useful for generating datasets or recording transaction traces
without requiring a live database connection.
"""

import os
import csv
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from py3_tpcc.drivers.abstractdriver import AbstractDriver
from py3_tpcc.drivers.registry import register_driver

logger = logging.getLogger(__name__)

@register_driver("csv")
class CsvDriver(AbstractDriver):
    """
    Outputs initial table data and executed transaction parameters to CSV files.
    """
    
    DEFAULT_CONFIG = {
        "table_directory": ("The path to the directory to store the table CSV files", "/tmp/tpcc-tables"),
        "txn_directory": ("The path to the directory to store the txn CSV files", "/tmp/tpcc-txns"),
    }
    
    def __init__(self, name: str, ddl: str):
        super().__init__("csv", ddl)
        self.table_directory: Optional[str] = None
        self.table_outputs: Dict[str, Any] = {}
        self.txn_directory: Optional[str] = None
        self.txn_outputs: Dict[str, Any] = {}
        self.txn_params: Dict[str, List[str]] = {}
    
    def make_default_config(self) -> Dict[str, Any]:
        """Generate the default configuration for this driver."""
        return self.DEFAULT_CONFIG
    
    def load_config(self, config: Any) -> Optional[Dict[str, Any]]:
        """Load configuration from the provided dictionary."""
        super()._load_config(config)
        
        # We need to make sure we're getting strings, not the original tuples
        # if the config hasn't been fully replaced
        tbl_val = self.config.get("table_directory", self.DEFAULT_CONFIG["table_directory"])
        self.table_directory = tbl_val[1] if isinstance(tbl_val, tuple) else tbl_val
        
        if not os.path.exists(self.table_directory):
            os.makedirs(self.table_directory)
            
        txn_val = self.config.get("txn_directory", self.DEFAULT_CONFIG["txn_directory"])
        self.txn_directory = txn_val[1] if isinstance(txn_val, tuple) else txn_val
        
        if not os.path.exists(self.txn_directory):
            os.makedirs(self.txn_directory)
            
        return self.config
        
    def connect(self) -> None:
        """Connecting for CSV driver simply means ensuring output directories exist."""
        logger.info(f"Writing CSV output to: tables={self.table_directory}, txns={self.txn_directory}")
        
    def reset(self) -> None:
        """Reset the CSV driver by closing open files and clearing dictionaries."""
        self.table_outputs.clear()
        self.txn_outputs.clear()
        self.txn_params.clear()
        
    def load_ddl(self) -> None:
        """No DDL to load for CSV driver."""
        pass
    
    def load_tuples(self, table_name: str, tuples: List[Any]) -> None:
        """Append rows to the corresponding table's CSV file."""
        if len(tuples) == 0:
            return
            
        if table_name not in self.table_outputs:
            path = os.path.join(self.table_directory, f"{table_name}.csv")
            # newline='' is important for csv module in python 3
            f = open(path, 'a', newline='')
            self.table_outputs[table_name] = csv.writer(f, quoting=csv.QUOTE_ALL)
            
        self.table_outputs[table_name].writerows(tuples)
        logger.debug(f"Wrote {len(tuples)} tuples to {table_name}.csv")
    
    def _execute_transaction(self, txn_name: str, params: Dict[str, Any]) -> Any:
        """Internal helper to write transaction parameters to a CSV file."""
        if txn_name not in self.txn_outputs:
            path = os.path.join(self.txn_directory, f"{txn_name}.csv")
            f = open(path, 'a', newline='')
            self.txn_outputs[txn_name] = csv.writer(f, quoting=csv.QUOTE_ALL)
            self.txn_params[txn_name] = list(params.keys())
            self.txn_outputs[txn_name].writerow(["Timestamp"] + self.txn_params[txn_name])
            
        row = [datetime.now()] + [params[k] for k in self.txn_params[txn_name]]
        self.txn_outputs[txn_name].writerow(row)
        return [] # Return empty result for transactions since CSV writer doesn't fetch data
        
    def do_delivery(self, params: Dict[str, Any]) -> Any:
        """Execute DELIVERY Transaction"""
        return self._execute_transaction("DELIVERY", params)
        
    def do_new_order(self, params: Dict[str, Any]) -> Any:
        """Execute NEW_ORDER Transaction"""
        return self._execute_transaction("NEW_ORDER", params)
        
    def do_order_status(self, params: Dict[str, Any]) -> Any:
        """Execute ORDER_STATUS Transaction"""
        return self._execute_transaction("ORDER_STATUS", params)
        
    def do_payment(self, params: Dict[str, Any]) -> Any:
        """Execute PAYMENT Transaction"""
        return self._execute_transaction("PAYMENT", params)
        
    def do_stock_level(self, params: Dict[str, Any]) -> Any:
        """Execute STOCK_LEVEL Transaction"""
        return self._execute_transaction("STOCK_LEVEL", params)

        