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

from datetime import datetime
import logging
import sys
import time
import traceback

from py3_tpcc import constants, results
from py3_tpcc.util import rand


class Executor:

    def __init__(
        self, driver, scale_parameters, stop_on_error=False, same_wh=85
    ):
        self.driver = driver
        self.scale_parameters = scale_parameters
        self.stop_on_error = stop_on_error
        self.same_wh = same_wh

    def run(self, duration):
        logging.info("Executing benchmark for %d seconds" % duration)

    def execute(self, duration):
        global_result = results.Results()
        assert global_result, "Failed to return a Results object"
        logging.debug("Executing benchmark for %d seconds" % duration)
        start = global_result.start_benchmark()
        debug = logging.getLogger().isEnabledFor(logging.DEBUG)
        # Batch Results
        batch_result = results.Results()
        start_batch = batch_result.start_benchmark()
        while (time.time() - start) <= duration:
            txn, params = self.do_one()
            global_txn_id = global_result.start_transaction(txn)
            batch_txn_id = batch_result.start_transaction(txn)
            if debug:
                logging.debug("Executing '%s' transaction" % txn)
            try:
                (val, retries) = self.driver.execute_transaction(txn, params)
            except KeyboardInterrupt:
                return -1
            except (Exception, AssertionError) as ex:
                logging.warn(
                    "Failed to execute Transaction '%s': %s" % (txn, ex)
                )
                traceback.print_exc(file=sys.stdout)
                print(
                    "Aborting some transaction with some error %s %s"
                    % (txn, ex)
                )
                global_result.abort_transaction(global_txn_id)
                batch_result.abort_transaction(batch_txn_id)
                if self.stop_on_error:
                    raise
                continue

            if val is None:
                global_result.abort_transaction(global_txn_id, retries)
                batch_result.abort_transaction(batch_txn_id, retries)
                continue

            batch_result.stop_transaction(batch_txn_id, retries)
            global_result.stop_transaction(global_txn_id, retries)

            if time.time() - start_batch > 1800:  # every 30 minutes
                batch_result.stop_benchmark()
                logging.info(batch_result.show())
                batch_result = results.Results()
                start_batch = batch_result.start_benchmark()

        batch_result.stop_benchmark()
        global_result.stop_benchmark()
        return global_result

    def do_one(self):
        """Selects and executes a transaction at random. The number of new order transactions executed per minute is the official "tpmC" metric. See TPC-C 5.4.2 (page 71)."""

        # This is not strictly accurate: The requirement is for certain
        # *minimum* percentages to be maintained. This is close to the right
        # thing, but not precisely correct. See TPC-C 5.2.4 (page 68).
        x = rand.number(1, 100)
        params = None
        txn = None

        # ========================================================================================
        # To debug use this to run a specific tpcc test. Run x=100 for new order before running other tests
        # x = 100 # new order
        # x = 44  # payment
        # x = 9   # order status
        # x = 7   # delivery
        # x = 3   # stock level
        # ========================================================================================

        if x <= 4:  # 4%
            txn, params = (
                constants.TransactionTypes.STOCK_LEVEL,
                self.generate_stock_level_params(),
            )
        elif x <= 4 + 4:  # 4%
            txn, params = (
                constants.TransactionTypes.DELIVERY,
                self.generate_delivery_params(),
            )
        elif x <= 4 + 4 + 4:  # 4%
            txn, params = (
                constants.TransactionTypes.ORDER_STATUS,
                self.generate_order_status_params(),
            )
        elif x <= 43 + 4 + 4 + 4:  # 43%
            txn, params = (
                constants.TransactionTypes.PAYMENT,
                self.generate_payment_params(),
            )
        else:  # 45%
            assert x > 100 - 45, (
                "Random number wasn't within specified range or percentages don't add up (%d)"
                % x
            )
            txn, params = (
                constants.TransactionTypes.NEW_ORDER,
                self.generate_new_order_params(),
            )

        return (txn, params)

    # generate_delivery_params
    def generate_delivery_params(self):
        """Return parameters for DELIVERY"""
        w_id = self.make_warehouse_id()
        o_carrier_id = rand.number(
            constants.MIN_CARRIER_ID, constants.MAX_CARRIER_ID
        )
        ol_delivery_d = datetime.now()
        return make_parameter_dict(
            locals(), "w_id", "o_carrier_id", "ol_delivery_d"
        )

    # generate_new_order_params
    def generate_new_order_params(self):
        """Return parameters for NEW_ORDER"""
        w_id = self.make_warehouse_id()
        d_id = self.make_district_id()
        c_id = self.make_customer_id()
        ol_cnt = rand.number(constants.MIN_OL_CNT, constants.MAX_OL_CNT)
        o_entry_d = datetime.now()

        # 1% of transactions roll back
        rollback = rand.number(1, 100) == 1

        i_ids = []
        i_w_ids = []
        i_qtys = []
        for i in range(0, ol_cnt):
            if rollback and i + 1 == ol_cnt:
                i_ids.append(self.scale_parameters.items + 1)
            else:
                i_id = self.make_item_id()
                while i_id in i_ids:
                    i_id = self.make_item_id()
                i_ids.append(i_id)

            # 1% of items are from a remote warehouse
            remote = rand.number(1, 100) == 1
            if self.scale_parameters.warehouses > 1 and remote:
                i_w_ids.append(
                    rand.number_excluding(
                        self.scale_parameters.starting_warehouse,
                        self.scale_parameters.ending_warehouse,
                        w_id,
                    )
                )
            else:
                i_w_ids.append(w_id)

            i_qtys.append(rand.number(1, constants.MAX_OL_QUANTITY))

        return make_parameter_dict(
            locals(),
            "w_id",
            "d_id",
            "c_id",
            "o_entry_d",
            "i_ids",
            "i_w_ids",
            "i_qtys",
        )

    # generate_order_status_params
    def generate_order_status_params(self):
        """Return parameters for ORDER_STATUS"""
        w_id = self.make_warehouse_id()
        d_id = self.make_district_id()
        c_last = None
        c_id = None

        # 60%: order status by last name
        if rand.number(1, 100) <= 60:
            c_last = rand.make_random_last_name(
                self.scale_parameters.customers_per_district
            )

        # 40%: order status by id
        else:
            c_id = self.make_customer_id()

        return make_parameter_dict(locals(), "w_id", "d_id", "c_id", "c_last")

    # generate_payment_params
    def generate_payment_params(self):
        """Return parameters for PAYMENT"""
        x = rand.number(1, 100)
        y = rand.number(1, 100)

        w_id = self.make_warehouse_id()
        d_id = self.make_district_id()
        c_w_id = None
        c_d_id = None
        c_id = None
        c_last = None
        h_amount = rand.fixed_point(
            2, constants.MIN_PAYMENT, constants.MAX_PAYMENT
        )
        h_date = datetime.now()

        # 85%: paying through own warehouse (or there is only 1 warehouse)
        if self.scale_parameters.warehouses == 1 or x <= self.same_wh:
            c_w_id = w_id
            c_d_id = d_id
        # 15%: paying through another warehouse:
        else:
            # select in range [1, num_warehouses] excluding w_id
            c_w_id = rand.number_excluding(
                self.scale_parameters.starting_warehouse,
                self.scale_parameters.ending_warehouse,
                w_id,
            )
            assert (
                c_w_id != w_id
            ), "Failed to generate W_ID that's not equal to C_W_ID"
            c_d_id = self.make_district_id()

        # 60%: payment by last name
        if y <= 60:
            c_last = rand.make_random_last_name(
                self.scale_parameters.customers_per_district
            )
        # 40%: payment by id
        else:
            assert y > 60, "Bad random payment value generated %d" % y
            c_id = self.make_customer_id()

        return make_parameter_dict(
            locals(),
            "w_id",
            "d_id",
            "h_amount",
            "c_w_id",
            "c_d_id",
            "c_id",
            "c_last",
            "h_date",
        )

    # generate_stock_level_params
    def generate_stock_level_params(self):
        """Returns parameters for STOCK_LEVEL"""
        w_id = self.make_warehouse_id()
        d_id = self.make_district_id()
        threshold = rand.number(
            constants.MIN_STOCK_LEVEL_THRESHOLD,
            constants.MAX_STOCK_LEVEL_THRESHOLD,
        )
        return make_parameter_dict(locals(), "w_id", "d_id", "threshold")

    def make_warehouse_id(self):
        w_id = rand.number(
            self.scale_parameters.starting_warehouse,
            self.scale_parameters.ending_warehouse,
        )
        assert w_id >= self.scale_parameters.starting_warehouse, (
            "Invalid W_ID: %d" % w_id
        )
        assert w_id <= self.scale_parameters.ending_warehouse, (
            "Invalid W_ID: %d" % w_id
        )
        return w_id

    def make_district_id(self):
        return rand.number(1, self.scale_parameters.districts_per_warehouse)

    def make_customer_id(self):
        return rand.nu_rand(
            1023, 1, self.scale_parameters.customers_per_district
        )

    def make_item_id(self):
        return rand.nu_rand(8191, 1, self.scale_parameters.items)


def make_parameter_dict(values, *args):
    return dict(map(lambda x: (x, values[x]), args))
