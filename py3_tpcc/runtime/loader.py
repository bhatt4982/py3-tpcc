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
from random import shuffle

from py3_tpcc import constants
from py3_tpcc.util import rand


class Loader:

    def __init__(self, driver, scale_parameters, w_ids, need_load_items):
        self.driver = driver
        self.scale_parameters = scale_parameters
        self.w_ids = w_ids
        self.batch_size = 2500
        self.need_load_items = need_load_items

    # execute
    def execute(self):

        # Item Table
        if self.need_load_items:
            logging.debug("Loading ITEM table")
            self.load_items()
            self.driver.load_endItem()

        # Then create the warehouse-specific tuples
        for w_id in self.w_ids:
            self.load_warehouse(w_id)
            self.driver.load_endWarehouse(w_id)

        return None

    # load_items
    def load_items(self):
        # Select 10% of the rows to be marked "original"
        original_rows = rand.select_unique_ids(
            self.scale_parameters.items // 10, 1, self.scale_parameters.items
        )

        # Load all of the items
        tuples = []
        total_tuples = 0
        for i in range(1, self.scale_parameters.items + 1):
            original = i in original_rows
            tuples.append(self.generate_item(i, original))
            total_tuples += 1
            if len(tuples) == self.batch_size:
                logging.debug(
                    "LOAD - %s: %5d / %d"
                    % (
                        constants.TABLENAME_ITEM,
                        total_tuples,
                        self.scale_parameters.items,
                    )
                )
                self.driver.load_tuples(constants.TABLENAME_ITEM, tuples)
                tuples = []
        if len(tuples) > 0:
            logging.debug(
                "LOAD - %s: %5d / %d"
                % (
                    constants.TABLENAME_ITEM,
                    total_tuples,
                    self.scale_parameters.items,
                )
            )
            self.driver.load_tuples(constants.TABLENAME_ITEM, tuples)

    # load_warehouse
    def load_warehouse(self, w_id):
        logging.debug(
            "LOAD - %s: %d / %d"
            % (constants.TABLENAME_WAREHOUSE, w_id, len(self.w_ids))
        )

        # WAREHOUSE
        w_tuples = [self.generate_warehouse(w_id)]
        self.driver.load_tuples(constants.TABLENAME_WAREHOUSE, w_tuples)

        # DISTRICT
        d_tuples = []
        for d_id in range(1, self.scale_parameters.districts_per_warehouse + 1):
            d_next_o_id = self.scale_parameters.customers_per_district + 1
            d_tuples = [self.generate_district(w_id, d_id, d_next_o_id)]

            c_tuples = []
            h_tuples = []

            # Select 10% of the customers to have bad credit
            selected_rows = rand.select_unique_ids(
                self.scale_parameters.customers_per_district // 10,
                1,
                self.scale_parameters.customers_per_district,
            )

            # TPC-C 4.3.3.1. says that o_c_id should be a permutation of [1, 3000]. But since it
            # is a c_id field, it seems to make sense to have it be a permutation of the
            # customers. For the "real" thing this will be equivalent
            c_id_permutation = []

            for c_id in range(
                1, self.scale_parameters.customers_per_district + 1
            ):
                bad_credit = c_id in selected_rows
                c_tuples.append(
                    self.generate_customer(w_id, d_id, c_id, bad_credit, True)
                )
                h_tuples.append(self.generate_history(w_id, d_id, c_id))
                c_id_permutation.append(c_id)
            assert c_id_permutation[0] == 1
            assert (
                c_id_permutation[
                    self.scale_parameters.customers_per_district - 1
                ]
                == self.scale_parameters.customers_per_district
            )
            shuffle(c_id_permutation)

            o_tuples = []
            ol_tuples = []
            no_tuples = []

            for o_id in range(
                1, self.scale_parameters.customers_per_district + 1
            ):
                o_ol_cnt = rand.number(
                    constants.MIN_OL_CNT, constants.MAX_OL_CNT
                )

                # The last new_orders_per_district are new orders
                new_order = (
                    self.scale_parameters.customers_per_district
                    - self.scale_parameters.new_orders_per_district
                ) < o_id
                o_tuples.append(
                    self.generate_order(
                        w_id,
                        d_id,
                        o_id,
                        c_id_permutation[o_id - 1],
                        o_ol_cnt,
                        new_order,
                    )
                )

                # Generate each OrderLine for the order
                for ol_number in range(0, o_ol_cnt):
                    ol_tuples.append(
                        self.generate_orderLine(
                            w_id,
                            d_id,
                            o_id,
                            ol_number,
                            self.scale_parameters.items,
                            new_order,
                        )
                    )

                # This is a new order: make one for it
                if new_order:
                    no_tuples.append([o_id, d_id, w_id])

            self.driver.load_tuples(constants.TABLENAME_DISTRICT, d_tuples)
            self.driver.load_tuples(constants.TABLENAME_CUSTOMER, c_tuples)
            self.driver.load_tuples(constants.TABLENAME_ORDERS, o_tuples)
            self.driver.load_tuples(constants.TABLENAME_ORDER_LINE, ol_tuples)
            self.driver.load_tuples(constants.TABLENAME_NEW_ORDER, no_tuples)
            self.driver.load_tuples(constants.TABLENAME_HISTORY, h_tuples)
            self.driver.load_endDistrict(w_id, d_id)

        # Select 10% of the stock to be marked "original"
        s_tuples = []
        selected_rows = rand.select_unique_ids(
            self.scale_parameters.items // 10, 1, self.scale_parameters.items
        )
        total_tuples = 0
        for i_id in range(1, self.scale_parameters.items + 1):
            original = i_id in selected_rows
            s_tuples.append(self.generate_stock(w_id, i_id, original))
            if len(s_tuples) >= self.batch_size:
                logging.debug(
                    "LOAD - %s [W_ID=%d]: %5d / %d"
                    % (
                        constants.TABLENAME_STOCK,
                        w_id,
                        total_tuples,
                        self.scale_parameters.items,
                    )
                )
                self.driver.load_tuples(constants.TABLENAME_STOCK, s_tuples)
                s_tuples = []
            total_tuples += 1
        if len(s_tuples) > 0:
            logging.debug(
                "LOAD - %s [W_ID=%d]: %5d / %d"
                % (
                    constants.TABLENAME_STOCK,
                    w_id,
                    total_tuples,
                    self.scale_parameters.items,
                )
            )
            self.driver.load_tuples(constants.TABLENAME_STOCK, s_tuples)

    # generate_item
    def generate_item(self, id, original):
        i_id = id
        i_im_id = rand.number(constants.MIN_IM, constants.MAX_IM)
        i_name = rand.astring(constants.MIN_I_NAME, constants.MAX_I_NAME)
        i_price = rand.fixed_point(
            constants.MONEY_DECIMALS, constants.MIN_PRICE, constants.MAX_PRICE
        )
        i_data = rand.astring(constants.MIN_I_DATA, constants.MAX_I_DATA)
        if original:
            i_data = self.fill_original(i_data)

        return [i_id, i_im_id, i_name, i_price, i_data]

    # generate_warehouse
    def generate_warehouse(self, w_id):
        w_tax = self.generate_tax()
        w_ytd = constants.INITIAL_W_YTD
        w_address = self.generate_address()
        return [w_id] + w_address + [w_tax, w_ytd]

    # generate_district
    def generate_district(self, d_w_id, d_id, d_next_o_id):
        d_tax = self.generate_tax()
        d_ytd = constants.INITIAL_D_YTD
        d_address = self.generate_address()
        return [d_id, d_w_id] + d_address + [d_tax, d_ytd, d_next_o_id]

    # generate_customer
    def generate_customer(
        self, c_w_id, c_d_id, c_id, bad_credit, does_replicate_name
    ):
        c_first = rand.astring(constants.MIN_FIRST, constants.MAX_FIRST)
        c_middle = constants.MIDDLE

        assert 1 <= c_id and c_id <= constants.CUSTOMERS_PER_DISTRICT
        if c_id <= 1000:
            c_last = rand.make_last_name(c_id - 1)
        else:
            c_last = rand.make_random_last_name(
                constants.CUSTOMERS_PER_DISTRICT
            )

        c_phone = rand.nstring(constants.PHONE, constants.PHONE)
        c_since = datetime.now()
        c_credit = constants.BAD_CREDIT if bad_credit else constants.GOOD_CREDIT
        c_credit_lim = constants.INITIAL_CREDIT_LIM
        c_discount = rand.fixed_point(
            constants.DISCOUNT_DECIMALS,
            constants.MIN_DISCOUNT,
            constants.MAX_DISCOUNT,
        )
        c_balance = constants.INITIAL_BALANCE
        c_ytd_payment = constants.INITIAL_YTD_PAYMENT
        c_payment_cnt = constants.INITIAL_PAYMENT_CNT
        c_delivery_cnt = constants.INITIAL_DELIVERY_CNT
        c_data = rand.astring(constants.MIN_C_DATA, constants.MAX_C_DATA)

        c_street1 = rand.astring(constants.MIN_STREET, constants.MAX_STREET)
        c_street2 = rand.astring(constants.MIN_STREET, constants.MAX_STREET)
        c_city = rand.astring(constants.MIN_CITY, constants.MAX_CITY)
        c_state = rand.astring(constants.STATE, constants.STATE)
        c_zip = self.generate_zip()

        return [
            c_id,
            c_d_id,
            c_w_id,
            c_first,
            c_middle,
            c_last,
            c_street1,
            c_street2,
            c_city,
            c_state,
            c_zip,
            c_phone,
            c_since,
            c_credit,
            c_credit_lim,
            c_discount,
            c_balance,
            c_ytd_payment,
            c_payment_cnt,
            c_delivery_cnt,
            c_data,
        ]

    # generate_order
    def generate_order(self, o_w_id, o_d_id, o_id, o_c_id, o_ol_cnt, new_order):
        """Returns the generated o_ol_cnt value."""
        o_entry_d = datetime.now()
        o_carrier_id = (
            constants.NULL_CARRIER_ID
            if new_order
            else rand.number(constants.MIN_CARRIER_ID, constants.MAX_CARRIER_ID)
        )
        o_all_local = constants.INITIAL_ALL_LOCAL
        return [
            o_id,
            o_c_id,
            o_d_id,
            o_w_id,
            o_entry_d,
            o_carrier_id,
            o_ol_cnt,
            o_all_local,
        ]

    # generate_orderLine
    def generate_orderLine(
        self, ol_w_id, ol_d_id, ol_o_id, ol_number, max_items, new_order
    ):
        ol_i_id = rand.number(1, max_items)
        ol_supply_w_id = ol_w_id
        ol_delivery_d = datetime.now()
        ol_quantity = constants.INITIAL_QUANTITY

        # 1% of items are from a remote warehouse
        remote = rand.number(1, 100) == 1
        if self.scale_parameters.warehouses > 1 and remote:
            ol_supply_w_id = rand.number_excluding(
                self.scale_parameters.starting_warehouse,
                self.scale_parameters.ending_warehouse,
                ol_w_id,
            )

        ol_amount = rand.fixed_point(
            constants.MONEY_DECIMALS,
            constants.MIN_AMOUNT,
            constants.MAX_PRICE * constants.MAX_OL_QUANTITY,
        )
        if new_order:
            ol_delivery_d = None
        ol_dist_info = rand.astring(constants.DIST, constants.DIST)

        return [
            ol_o_id,
            ol_d_id,
            ol_w_id,
            ol_number,
            ol_i_id,
            ol_supply_w_id,
            ol_delivery_d,
            ol_quantity,
            ol_amount,
            ol_dist_info,
        ]

    # generate_stock
    def generate_stock(self, s_w_id, s_i_id, original):
        s_quantity = rand.number(constants.MIN_QUANTITY, constants.MAX_QUANTITY)
        s_ytd = 0
        s_order_cnt = 0
        s_remote_cnt = 0

        s_data = rand.astring(constants.MIN_I_DATA, constants.MAX_I_DATA)
        if original:
            self.fill_original(s_data)

        s_dists = []
        for i in range(0, constants.DISTRICTS_PER_WAREHOUSE):
            s_dists.append(rand.astring(constants.DIST, constants.DIST))

        return (
            [s_i_id, s_w_id, s_quantity]
            + s_dists
            + [s_ytd, s_order_cnt, s_remote_cnt, s_data]
        )

    # generate_history
    def generate_history(self, h_c_w_id, h_c_d_id, h_c_id):
        h_w_id = h_c_w_id
        h_d_id = h_c_d_id
        h_date = datetime.now()
        h_amount = constants.INITIAL_AMOUNT
        h_data = rand.astring(constants.MIN_DATA, constants.MAX_DATA)
        return [
            h_c_id,
            h_c_d_id,
            h_c_w_id,
            h_d_id,
            h_w_id,
            h_date,
            h_amount,
            h_data,
        ]

    # generate_address
    def generate_address(self):
        """
        Returns a name and a street address
        Used by both generate_warehouse and generate_district.
        """
        name = rand.astring(constants.MIN_NAME, constants.MAX_NAME)
        return [name] + self.generate_street_address()

    # generate_street_address
    def generate_street_address(self):
        """
        Returns a list for a street address
        Used for warehouses, districts and customers.
        """
        street1 = rand.astring(constants.MIN_STREET, constants.MAX_STREET)
        street2 = rand.astring(constants.MIN_STREET, constants.MAX_STREET)
        city = rand.astring(constants.MIN_CITY, constants.MAX_CITY)
        state = rand.astring(constants.STATE, constants.STATE)
        zip = self.generate_zip()

        return [street1, street2, city, state, zip]

    # generate_tax
    def generate_tax(self):
        return rand.fixed_point(
            constants.TAX_DECIMALS, constants.MIN_TAX, constants.MAX_TAX
        )

    # generate_zip
    def generate_zip(self):
        length = constants.ZIP_LENGTH - len(constants.ZIP_SUFFIX)
        return rand.nstring(length, length) + constants.ZIP_SUFFIX

    # fill_original
    def fill_original(self, data):
        """
        a string with ORIGINAL_STRING at a random position
        """
        original_length = len(constants.ORIGINAL_STRING)
        position = rand.number(0, len(data) - original_length)
        out = (
            data[:position]
            + constants.ORIGINAL_STRING
            + data[position + original_length :]
        )
        assert len(out) == len(data)
        return out
