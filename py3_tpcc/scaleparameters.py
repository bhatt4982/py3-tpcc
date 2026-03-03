#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
# Copyright (C) 2011
# Andy Pavlo & Yang Lu
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

from py3_tpcc import constants


class ScaleParameters:
    def __init__(
        self,
        items,
        warehouses,
        districts_per_warehouse,
        customers_per_district,
        new_orders_per_district,
    ):
        assert 1 <= items and items <= constants.NUM_ITEMS
        self.items = items
        assert warehouses > 0
        self.warehouses = warehouses
        self.starting_warehouse = 1
        assert (
            1 <= districts_per_warehouse
            and districts_per_warehouse <= constants.DISTRICTS_PER_WAREHOUSE
        )
        self.districts_per_warehouse = districts_per_warehouse
        assert (
            1 <= customers_per_district
            and customers_per_district <= constants.CUSTOMERS_PER_DISTRICT
        )
        self.customers_per_district = customers_per_district
        assert (
            0 <= new_orders_per_district
            and new_orders_per_district <= constants.CUSTOMERS_PER_DISTRICT
        )
        assert (
            new_orders_per_district <= constants.INITIAL_NEW_ORDERS_PER_DISTRICT
        )
        self.new_orders_per_district = new_orders_per_district
        self.ending_warehouse = self.warehouses + self.starting_warehouse - 1

    def __str__(self):
        out = "%d items\n" % self.items
        out += "%d warehouses\n" % self.warehouses
        out += "%d districts/warehouse\n" % self.districts_per_warehouse
        out += "%d customers/district\n" % self.customers_per_district
        out += "%d initial new orders/district" % self.new_orders_per_district
        return out

    @classmethod
    def makeDefault(warehouses) -> "ScaleParameters":
        return ScaleParameters(
            constants.NUM_ITEMS,
            warehouses,
            constants.DISTRICTS_PER_WAREHOUSE,
            constants.CUSTOMERS_PER_DISTRICT,
            constants.INITIAL_NEW_ORDERS_PER_DISTRICT,
        )

    @classmethod
    def makeWithScaleFactor(cls, warehouses, scalefactor) -> "ScaleParameters":
        assert scalefactor >= 1.0

        items = int(constants.NUM_ITEMS / scalefactor)
        if items <= 0:
            items = 1
        districts = int(max(constants.DISTRICTS_PER_WAREHOUSE, 1))
        customers = int(max(constants.CUSTOMERS_PER_DISTRICT / scalefactor, 1))
        neworders = int(
            max(constants.INITIAL_NEW_ORDERS_PER_DISTRICT / scalefactor, 0)
        )

        return ScaleParameters(
            items, warehouses, districts, customers, neworders
        )
