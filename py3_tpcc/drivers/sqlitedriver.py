# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
# Copyright (C) 2011
# Andy Pavlo
# http://www.cs.brown.edu/~pavlo/
#
# Original Java Version:
# Copyright (C) 2008
# Evan Jones
# Massachusetts Institute of Technology
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

import logging
import os
from pprint import pformat
import sqlite3
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from py3_tpcc import constants
from py3_tpcc.drivers.abstractdriver import AbstractDriver
from py3_tpcc.drivers.registry import register_driver

logger = logging.getLogger(__name__)

TXN_QUERIES = {
    "DELIVERY": {
        "getNewOrder": (
            "SELECT NO_O_ID FROM NEW_ORDER WHERE NO_D_ID = ? AND NO_W_ID = ? AND NO_O_ID > -1 LIMIT 1"
        ),
        "deleteNewOrder": "DELETE FROM NEW_ORDER WHERE NO_D_ID = ? AND NO_W_ID = ? AND NO_O_ID = ?",
        "getCId": "SELECT O_C_ID FROM ORDERS WHERE O_ID = ? AND O_D_ID = ? AND O_W_ID = ?",
        "updateOrders": "UPDATE ORDERS SET O_CARRIER_ID = ? WHERE O_ID = ? AND O_D_ID = ? AND O_W_ID = ?",
        "updateOrderLine": "UPDATE ORDER_LINE SET OL_DELIVERY_D = ? WHERE OL_O_ID = ? AND OL_D_ID = ? AND OL_W_ID = ?",
        "sumOLAmount": "SELECT SUM(OL_AMOUNT) AS SUM_OL_AMOUNT FROM ORDER_LINE WHERE OL_O_ID = ? AND OL_D_ID = ? AND OL_W_ID = ?",
        "updateCustomer": "UPDATE CUSTOMER SET C_BALANCE = C_BALANCE + ? WHERE C_ID = ? AND C_D_ID = ? AND C_W_ID = ?",
    },
    "NEW_ORDER": {
        "getWarehouseTaxRate": "SELECT W_TAX FROM WAREHOUSE WHERE W_ID = ?",
        "getDistrict": "SELECT D_TAX, D_NEXT_O_ID FROM DISTRICT WHERE D_ID = ? AND D_W_ID = ?",
        "incrementNextOrderId": "UPDATE DISTRICT SET D_NEXT_O_ID = ? WHERE D_ID = ? AND D_W_ID = ?",
        "getCustomer": "SELECT C_DISCOUNT, C_LAST, C_CREDIT FROM CUSTOMER WHERE C_W_ID = ? AND C_D_ID = ? AND C_ID = ?",
        "createOrder": "INSERT INTO ORDERS (O_ID, O_D_ID, O_W_ID, O_C_ID, O_ENTRY_D, O_CARRIER_ID, O_OL_CNT, O_ALL_LOCAL) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        "createNewOrder": "INSERT INTO NEW_ORDER (NO_O_ID, NO_D_ID, NO_W_ID) VALUES (?, ?, ?)",
        "getItemInfo": "SELECT I_PRICE, I_NAME, I_DATA FROM ITEM WHERE I_ID = ?",
        "getStockInfo": "SELECT S_QUANTITY, S_DATA, S_YTD, S_ORDER_CNT, S_REMOTE_CNT, S_DIST_%02d FROM STOCK WHERE S_I_ID = ? AND S_W_ID = ?",
        "updateStock": "UPDATE STOCK SET S_QUANTITY = ?, S_YTD = ?, S_ORDER_CNT = ?, S_REMOTE_CNT = ? WHERE S_I_ID = ? AND S_W_ID = ?",
        "createOrderLine": "INSERT INTO ORDER_LINE (OL_O_ID, OL_D_ID, OL_W_ID, OL_NUMBER, OL_I_ID, OL_SUPPLY_W_ID, OL_DELIVERY_D, OL_QUANTITY, OL_AMOUNT, OL_DIST_INFO) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    },
    "ORDER_STATUS": {
        "getCustomerByCustomerId": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_BALANCE FROM CUSTOMER WHERE C_W_ID = ? AND C_D_ID = ? AND C_ID = ?",
        "getCustomersByLastName": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_BALANCE FROM CUSTOMER WHERE C_W_ID = ? AND C_D_ID = ? AND C_LAST = ? ORDER BY C_FIRST",
        "getLastOrder": "SELECT O_ID, O_CARRIER_ID, O_ENTRY_D FROM ORDERS WHERE O_W_ID = ? AND O_D_ID = ? AND O_C_ID = ? ORDER BY O_ID DESC LIMIT 1",
        "getOrderLines": "SELECT OL_SUPPLY_W_ID, OL_I_ID, OL_QUANTITY, OL_AMOUNT, OL_DELIVERY_D FROM ORDER_LINE WHERE OL_W_ID = ? AND OL_D_ID = ? AND OL_O_ID = ?",
    },
    "PAYMENT": {
        "getWarehouse": "SELECT W_NAME, W_STREET_1, W_STREET_2, W_CITY, W_STATE, W_ZIP FROM WAREHOUSE WHERE W_ID = ?",
        "updateWarehouseBalance": "UPDATE WAREHOUSE SET W_YTD = W_YTD + ? WHERE W_ID = ?",
        "getDistrict": "SELECT D_NAME, D_STREET_1, D_STREET_2, D_CITY, D_STATE, D_ZIP FROM DISTRICT WHERE D_W_ID = ? AND D_ID = ?",
        "updateDistrictBalance": "UPDATE DISTRICT SET D_YTD = D_YTD + ? WHERE D_W_ID  = ? AND D_ID = ?",
        "getCustomerByCustomerId": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_STREET_1, C_STREET_2, C_CITY, C_STATE, C_ZIP, C_PHONE, C_SINCE, C_CREDIT, C_CREDIT_LIM, C_DISCOUNT, C_BALANCE, C_YTD_PAYMENT, C_PAYMENT_CNT, C_DATA FROM CUSTOMER WHERE C_W_ID = ? AND C_D_ID = ? AND C_ID = ?",
        "getCustomersByLastName": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_STREET_1, C_STREET_2, C_CITY, C_STATE, C_ZIP, C_PHONE, C_SINCE, C_CREDIT, C_CREDIT_LIM, C_DISCOUNT, C_BALANCE, C_YTD_PAYMENT, C_PAYMENT_CNT, C_DATA FROM CUSTOMER WHERE C_W_ID = ? AND C_D_ID = ? AND C_LAST = ? ORDER BY C_FIRST",
        "updateBCCustomer": "UPDATE CUSTOMER SET C_BALANCE = ?, C_YTD_PAYMENT = ?, C_PAYMENT_CNT = ?, C_DATA = ? WHERE C_W_ID = ? AND C_D_ID = ? AND C_ID = ?",
        "updateGCCustomer": "UPDATE CUSTOMER SET C_BALANCE = ?, C_YTD_PAYMENT = ?, C_PAYMENT_CNT = ? WHERE C_W_ID = ? AND C_D_ID = ? AND C_ID = ?",
        "insertHistory": "INSERT INTO HISTORY VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    },
    "STOCK_LEVEL": {
        "getOId": "SELECT D_NEXT_O_ID FROM DISTRICT WHERE D_W_ID = ? AND D_ID = ?",
        "getStockCount": """
            SELECT COUNT(DISTINCT(OL_I_ID)) AS STOCK_COUNT FROM ORDER_LINE, STOCK
            WHERE OL_W_ID = ?
              AND OL_D_ID = ?
              AND OL_O_ID < ?
              AND OL_O_ID >= ?
              AND S_W_ID = ?
              AND S_I_ID = OL_I_ID
              AND S_QUANTITY < ?
        """,
    },
}


@register_driver("sqlite")
class SQLiteDriver(AbstractDriver):

    CONFIG_FILE = "sqlite.toml"

    def make_default_config(self) -> Dict[str, Any]:
        config_path = os.path.join(
            os.path.dirname(__file__), SQLiteDriver.CONFIG_FILE
        )
        return self._read_config(config_path)

    def load_config(self, config: Any) -> Optional[Dict[str, Any]]:
        super()._load_config(config)

        self.database = str(self.config.get("database", "JUNK"))

        # if self.config.get("reset") and os.path.exists(self.database):
        #     logger.debug(f"Deleting database '{self.database}'")
        #     os.unlink(self.database)

        # if not os.path.exists(self.database):
        #     logger.debug(f"Loading DDL file '{self.ddl}'")
        #     cmd = f"sqlite3 {self.database} < {self.ddl}"
        #     (result, output) = subprocess.getstatusoutput(cmd)
        #     assert result == 0, f"{cmd}\n{output}"

        return self.config

    def connect(self) -> None:
        logger.info("Connecting to database: %s", self.database)
        try:
            self.reset()
            self.load_ddl()
            self.conn = sqlite3.connect(self.database, timeout=60.0)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database {self.database}: {e}")

        if not self.conn:
            raise ConnectionError(f"Connection must be established with database {self.database}")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def reset(self) -> None:
        """Reset the database."""
        if os.path.exists(self.database):
            logger.debug(f"Deleting database '{self.database}'")
            os.unlink(self.database)

    def load_ddl(self) -> None:
        """Load the DDL file."""
        if not os.path.exists(self.database):
            logger.debug(f"Loading DDL file '{self.ddl}'")
            cmd = f"sqlite3 {self.database} < {self.ddl}"
            (result, output) = subprocess.getstatusoutput(cmd)
            assert result == 0, f"{cmd}\n{output}"

    def __init__(self, name: str, ddl: str):
        super().__init__("sqlite", ddl)
        self.database: Optional[str] = None
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def load_tuples(self, table_name: str, tuples: List[Any]) -> None:
        if len(tuples) == 0:
            return

        p = ["?"] * len(tuples[0])
        sql = f"INSERT INTO {table_name} VALUES ({','.join(p)})"
        self.cursor.executemany(sql, tuples)

        logger.debug(
            f"Loaded {len(tuples)} tuples for table_name {table_name}"
        )
        return

    def load_finish(self) -> None:
        logger.info("Commiting changes to database")
        self.conn.commit()

    def do_delivery(self, params: Dict[str, Any]) -> List[Tuple[int, int]]:
        q = TXN_QUERIES["DELIVERY"]

        w_id = params["w_id"]
        o_carrier_id = params["o_carrier_id"]
        ol_delivery_d = params["ol_delivery_d"]

        result = []
        with self.conn:
            for d_id in range(1, constants.DISTRICTS_PER_WAREHOUSE + 1):
                self.cursor.execute(q["getNewOrder"], (d_id, w_id))
                newOrder = self.cursor.fetchone()
                if newOrder is None:
                    continue
                assert len(newOrder) > 0
                no_o_id = newOrder[0]

                self.cursor.execute(q["getCId"], (no_o_id, d_id, w_id))
                c_id = self.cursor.fetchone()[0]

                self.cursor.execute(q["sumOLAmount"], (no_o_id, d_id, w_id))
                ol_total = self.cursor.fetchone()[0]

                self.cursor.execute(q["deleteNewOrder"], (d_id, w_id, no_o_id))
                self.cursor.execute(
                    q["updateOrders"], (o_carrier_id, no_o_id, d_id, w_id)
                )
                self.cursor.execute(
                    q["updateOrderLine"], (ol_delivery_d, no_o_id, d_id, w_id)
                )

                assert (
                    ol_total is not None
                ), "ol_total is NULL: there are no order lines. This should not happen"
                assert ol_total > 0.0

                self.cursor.execute(
                    q["updateCustomer"], (ol_total, c_id, d_id, w_id)
                )

                result.append((d_id, no_o_id))

        return result

    def do_new_order(self, params: Dict[str, Any]) -> Optional[List[Any]]:
        q = TXN_QUERIES["NEW_ORDER"]

        w_id = params["w_id"]
        d_id = params["d_id"]
        c_id = params["c_id"]
        o_entry_d = params["o_entry_d"]
        i_ids = params["i_ids"]
        i_w_ids = params["i_w_ids"]
        i_qtys = params["i_qtys"]

        assert len(i_ids) > 0
        assert len(i_ids) == len(i_w_ids)
        assert len(i_ids) == len(i_qtys)

        all_local = True
        items = []

        try:
            with self.conn:
                for i in range(len(i_ids)):
                    all_local = all_local and i_w_ids[i] == w_id
                    self.cursor.execute(q["getItemInfo"], [i_ids[i]])
                    items.append(self.cursor.fetchone())
                assert len(items) == len(i_ids)

                for item in items:
                    if not item or len(item) == 0:
                        self.conn.rollback()
                        return None

                self.cursor.execute(q["getWarehouseTaxRate"], [w_id])
                w_tax = self.cursor.fetchone()[0]

                self.cursor.execute(q["getDistrict"], [d_id, w_id])
                district_info = self.cursor.fetchone()
                d_tax = district_info[0]
                d_next_o_id = district_info[1]

                self.cursor.execute(q["getCustomer"], [w_id, d_id, c_id])
                customer_info = self.cursor.fetchone()
                c_discount = customer_info[0]

                ol_cnt = len(i_ids)
                o_carrier_id = constants.NULL_CARRIER_ID

                self.cursor.execute(
                    q["incrementNextOrderId"], [d_next_o_id + 1, d_id, w_id]
                )
                self.cursor.execute(
                    q["createOrder"],
                    [
                        d_next_o_id,
                        d_id,
                        w_id,
                        c_id,
                        o_entry_d,
                        o_carrier_id,
                        ol_cnt,
                        all_local,
                    ],
                )
                self.cursor.execute(
                    q["createNewOrder"], [d_next_o_id, d_id, w_id]
                )

                item_data = []
                total = 0
                for i in range(len(i_ids)):
                    ol_number = i + 1
                    ol_supply_w_id = i_w_ids[i]
                    ol_i_id = i_ids[i]
                    ol_quantity = i_qtys[i]

                    itemInfo = items[i]
                    i_name = itemInfo[1]
                    i_data = itemInfo[2]
                    i_price = itemInfo[0]

                    self.cursor.execute(
                        q["getStockInfo"] % (d_id), [ol_i_id, ol_supply_w_id]
                    )
                    stockInfo = self.cursor.fetchone()
                    if len(stockInfo) == 0:
                        logger.warning(
                            f"No STOCK record for (ol_i_id={ol_i_id}, ol_supply_w_id={ol_supply_w_id})"
                        )
                        continue
                    s_quantity = stockInfo[0]
                    s_ytd = stockInfo[2]
                    s_order_cnt = stockInfo[3]
                    s_remote_cnt = stockInfo[4]
                    s_data = stockInfo[1]
                    s_dist_xx = stockInfo[5]

                    s_ytd += ol_quantity
                    if s_quantity >= ol_quantity + 10:
                        s_quantity = s_quantity - ol_quantity
                    else:
                        s_quantity = s_quantity + 91 - ol_quantity
                    s_order_cnt += 1

                    if ol_supply_w_id != w_id:
                        s_remote_cnt += 1

                    self.cursor.execute(
                        q["updateStock"],
                        [
                            s_quantity,
                            s_ytd,
                            s_order_cnt,
                            s_remote_cnt,
                            ol_i_id,
                            ol_supply_w_id,
                        ],
                    )

                    if (
                        i_data.find(constants.ORIGINAL_STRING) != -1
                        and s_data.find(constants.ORIGINAL_STRING) != -1
                    ):
                        brand_generic = "B"
                    else:
                        brand_generic = "G"

                    ol_amount = ol_quantity * i_price
                    total += ol_amount

                    self.cursor.execute(
                        q["createOrderLine"],
                        [
                            d_next_o_id,
                            d_id,
                            w_id,
                            ol_number,
                            ol_i_id,
                            ol_supply_w_id,
                            o_entry_d,
                            ol_quantity,
                            ol_amount,
                            s_dist_xx,
                        ],
                    )

                    item_data.append(
                        (i_name, s_quantity, brand_generic, i_price, ol_amount)
                    )

        except Exception as e:
            raise e

        total *= (1 - c_discount) * (1 + w_tax + d_tax)
        misc = [(w_tax, d_tax, d_next_o_id, total)]

        return [customer_info, misc, item_data]

    def do_order_status(self, params: Dict[str, Any]) -> List[Any]:
        q = TXN_QUERIES["ORDER_STATUS"]

        w_id = params["w_id"]
        d_id = params["d_id"]
        c_id = params["c_id"]
        c_last = params["c_last"]

        assert w_id, pformat(params)
        assert d_id, pformat(params)

        with self.conn:
            if c_id is not None:
                self.cursor.execute(
                    q["getCustomerByCustomerId"], (w_id, d_id, c_id)
                )
                customer = self.cursor.fetchone()
            else:
                self.cursor.execute(
                    q["getCustomersByLastName"], (w_id, d_id, c_last)
                )
                all_customers = self.cursor.fetchall()
                if not all_customers or len(all_customers) == 0:
                    self.conn.rollback()
                    return None
                namecnt = len(all_customers)
                index = int((namecnt - 1) / 2)
                customer = all_customers[index]
                c_id = customer[0]
            if not customer or len(customer) == 0:
                self.conn.rollback()
                return None
            assert c_id is not None

            self.cursor.execute(q["getLastOrder"], (w_id, d_id, c_id))
            order = self.cursor.fetchone()
            if order:
                self.cursor.execute(q["getOrderLines"], (w_id, d_id, order[0]))
                orderLines = self.cursor.fetchall()
            else:
                orderLines = []

        return [customer, order, orderLines]

    def do_payment(self, params: Dict[str, Any]) -> List[Any]:
        q = TXN_QUERIES["PAYMENT"]

        w_id = params["w_id"]
        d_id = params["d_id"]
        h_amount = params["h_amount"]
        c_w_id = params["c_w_id"]
        c_d_id = params["c_d_id"]
        c_id = params["c_id"]
        c_last = params["c_last"]
        h_date = params["h_date"]

        with self.conn:
            if c_id is not None:
                self.cursor.execute(
                    q["getCustomerByCustomerId"], (w_id, d_id, c_id)
                )
                customer = self.cursor.fetchone()
            else:
                self.cursor.execute(
                    q["getCustomersByLastName"], (w_id, d_id, c_last)
                )
                all_customers = self.cursor.fetchall()
                if not all_customers or len(all_customers) == 0:
                    self.conn.rollback()
                    return None
                namecnt = len(all_customers)
                index = int((namecnt - 1) / 2)
                customer = all_customers[index]
                c_id = customer[0]
            if not customer or len(customer) == 0:
                self.conn.rollback()
                return None
            c_balance = customer["C_BALANCE"] - h_amount
            c_ytd_payment = customer["C_YTD_PAYMENT"] + h_amount
            c_payment_cnt = customer["C_PAYMENT_CNT"] + 1
            c_data = customer["C_DATA"]

            self.cursor.execute(q["getWarehouse"], (w_id,))
            warehouse = self.cursor.fetchone()

            self.cursor.execute(q["getDistrict"], (w_id, d_id))
            district = self.cursor.fetchone()

            self.cursor.execute(q["updateWarehouseBalance"], (h_amount, w_id))
            self.cursor.execute(
                q["updateDistrictBalance"], (h_amount, w_id, d_id)
            )

            if customer["C_CREDIT"] == constants.BAD_CREDIT:
                newData = " ".join(
                    map(str, [c_id, c_d_id, c_w_id, d_id, w_id, h_amount])
                )
                c_data = newData + "|" + c_data
                if len(c_data) > constants.MAX_C_DATA:
                    c_data = c_data[: constants.MAX_C_DATA]
                self.cursor.execute(
                    q["updateBCCustomer"],
                    (
                        c_balance,
                        c_ytd_payment,
                        c_payment_cnt,
                        c_data,
                        c_w_id,
                        c_d_id,
                        c_id,
                    ),
                )
            else:
                c_data = ""
                self.cursor.execute(
                    q["updateGCCustomer"],
                    (
                        c_balance,
                        c_ytd_payment,
                        c_payment_cnt,
                        c_w_id,
                        c_d_id,
                        c_id,
                    ),
                )

            h_data = f"{warehouse['W_NAME']}    {district['D_NAME']}"
            self.cursor.execute(
                q["insertHistory"],
                (c_id, c_d_id, c_w_id, d_id, w_id, h_date, h_amount, h_data),
            )

        return [warehouse, district, customer]

    def do_stock_level(self, params: Dict[str, Any]) -> int:
        q = TXN_QUERIES["STOCK_LEVEL"]

        w_id = params["w_id"]
        d_id = params["d_id"]
        threshold = params["threshold"]

        with self.conn:
            self.cursor.execute(q["getOId"], [w_id, d_id])
            result = self.cursor.fetchone()
            if not result or len(result) == 0:
                self.conn.rollback()
                return 0
            o_id = result[0]

            self.cursor.execute(
                q["getStockCount"],
                [w_id, d_id, o_id, (o_id - 20), w_id, threshold],
            )
            result = self.cursor.fetchone()

        return int(result[0])
