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

from . import rand


def make_for_load():
    """Create random NURand constants, appropriate for loading the database."""
    c_last = rand.number(0, 255)
    c_id = rand.number(0, 1023)
    order_line_item_id = rand.number(0, 8191)
    return NURandC(c_last, c_id, order_line_item_id)


def valid_c_run(c_run, c_load):
    """Returns true if the cRun value is valid for running. See TPC-C 2.1.6.1 (page 20)"""
    c_delta = abs(c_run - c_load)
    return 65 <= c_delta <= 119 and c_delta != 96 and c_delta != 112


def make_for_run(load_c):
    """Create random NURand constants for running TPC-C."""
    c_run = rand.number(0, 255)
    while not valid_c_run(c_run, load_c.c_last):
        c_run = rand.number(0, 255)
    assert valid_c_run(c_run, load_c.c_last)

    c_id = rand.number(0, 1023)
    order_line_item_id = rand.number(0, 8191)
    return NURandC(c_run, c_id, order_line_item_id)


class NURandC:
    def __init__(self, c_last, c_id, order_line_item_id):
        self.c_last = c_last
        self.c_id = c_id
        self.order_line_item_id = order_line_item_id
