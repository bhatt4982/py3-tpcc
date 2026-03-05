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

"""
TPC-C Randomized Value Generators

Provides controlled random data generation compliant with the strict rules
of the TPC-C specification, including non-uniform random distributions,
fixed-point float generations, and TPC-C specific syllable strings.
"""

import random

from . import nurand

SYLLABLES = [
    "BAR",
    "OUGHT",
    "ABLE",
    "PRI",
    "PRES",
    "ESE",
    "ANTI",
    "CALLY",
    "ATION",
    "EING",
]

nurand_var = None  # NURand


def set_nu_rand(nu):
    global nurand_var
    nurand_var = nu


def nu_rand(a, x, y):
    """A non-uniform random number, as defined by TPC-C 2.1.6. (page 20)."""
    assert x <= y
    if nurand_var is None:
        set_nu_rand(nurand.make_for_load())

    if a == 255:
        c = nurand_var.c_last
    elif a == 1023:
        c = nurand_var.c_id
    elif a == 8191:
        c = nurand_var.order_line_item_id
    else:
        raise Exception(f"a = {a} is not a supported value")

    return (((number(0, a) | number(x, y)) + c) % (y - x + 1)) + x


def number(minimum, maximum):
    value = random.randint(minimum, maximum)
    assert minimum <= value and value <= maximum
    return value


def number_excluding(minimum, maximum, excluding):
    """An in the range [minimum, maximum], excluding excluding."""
    assert minimum < maximum
    assert minimum <= excluding and excluding <= maximum

    # Generate 1 less number than the range
    num = number(minimum, maximum - 1)

    # Adjust the numbers to remove excluding
    if num >= excluding:
        num += 1
    assert minimum <= num and num <= maximum and num != excluding
    return num


def fixed_point(decimal_places, minimum, maximum):
    assert decimal_places > 0
    assert minimum < maximum

    multiplier = 1
    for i in range(0, decimal_places):
        multiplier *= 10

    int_min = int(minimum * multiplier + 0.5)
    int_max = int(maximum * multiplier + 0.5)

    return float(number(int_min, int_max) / float(multiplier))


def select_unique_ids(num_unique, minimum, maximum):
    rows = set()
    for _ in range(0, num_unique):
        index = None
        while index is None or index in rows:
            index = number(minimum, maximum)
        rows.add(index)
    assert len(rows) == num_unique
    return rows


def astring(minimum_length, maximum_length):
    """A random alphabetic string with length in range."""
    return random_string(minimum_length, maximum_length, "a", 26)


def nstring(minimum_length, maximum_length):
    """A random numeric string with length in range."""
    return random_string(minimum_length, maximum_length, "0", 10)


def random_string(minimum_length, maximum_length, base, num_characters):
    length = number(minimum_length, maximum_length)
    base_byte = ord(base)
    string = ""
    for _ in range(length):
        string += chr(base_byte + number(0, num_characters - 1))
    return string


def make_last_name(num):
    """A last name as defined by TPC-C 4.3.2.3. Not actually random."""
    assert 0 <= num <= 999
    indicies = [num // 100, (num // 10) % 10, num % 10]
    return "".join(map(lambda x: SYLLABLES[x], indicies))


def make_random_last_name(max_cid):
    """A non-uniform random last name, as defined by TPC-C."""
    min_cid = 999
    if (max_cid - 1) < min_cid:
        min_cid = max_cid - 1
    return make_last_name(nu_rand(255, 0, min_cid))
