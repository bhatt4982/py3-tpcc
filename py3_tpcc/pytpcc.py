#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys

# Ensure we can import py3_tpcc when running as a script
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to trigger registration
from py3_tpcc.drivers.registry import getDrivers
import py3_tpcc.drivers.spannerdriver  # noqa: F401
import py3_tpcc.drivers.sqlitedriver  # noqa: F401

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Python TPC-C Benchmark Driver"
    )

    # Dynamic choices for positional argument
    available_drivers = getDrivers()
    drivers_str = (
        ", ".join(available_drivers) if available_drivers else "None found"
    )

    # Positional Arguments
    parser.add_argument(
        "system",
        choices=available_drivers if available_drivers else None,
        help="Specifies the target database system driver to use. "
        f"Available drivers: {drivers_str}",
    )

    # Optional Arguments
    parser.add_argument(
        "--config", type=str, help="Path to the driver configuration file."
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Instructs the driver to reset the contents of the database.",
    )

    parser.add_argument(
        "--scalefactor",
        type=float,
        default=1,
        help="Benchmark scale factor. Default: 1",
    )

    parser.add_argument(
        "--warehouses",
        type=int,
        default=4,
        help="Number of Warehouses to simulate. Default: 4",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="How long to run the benchmark in seconds. Default: 60",
    )

    parser.add_argument(
        "--ddl",
        type=str,
        default="tpcc.sql",
        help="Path to the TPC-C DDL SQL file. Default: tpcc.sql",
    )

    parser.add_argument(
        "--clients",
        type=int,
        default=1,
        help=(
            "The number of blocking clients (processes) to fork for "
            "parallel execution. Default: 1"
        ),
    )

    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help=(
            "Stop the transaction execution immediately "
            "if the driver throws an exception."
        ),
    )

    parser.add_argument(
        "--no-load",
        action="store_true",
        help=(
            "Disables the data loading phase "
            "(useful if the DB is already populated)."
        ),
    )

    parser.add_argument(
        "--no-execute",
        action="store_true",
        help=(
            "Disables the workload execution phase "
            "(useful if you only want to load data)."
        ),
    )

    parser.add_argument(
        "--print-config",
        action="store_true",
        help=(
            "Prints the default configuration file for the "
            "selected system and exits."
        ),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enables debug-level logging messages.",
    )

    # If no arguments provided, print help
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # For verification/stub purposes
    logger.info(f"Selected System: {args.system}")
    logger.info(f"Configuration: {args}")


if __name__ == "__main__":
    main()
