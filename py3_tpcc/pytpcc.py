#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
# Copyright (C) 2011
# Andy Pavlo & Yang Lu
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


import argparse
import asyncio
import logging
import os
import subprocess
import sys
import time

# Ensure we can import py3_tpcc when running as a script
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

# Import modules to trigger registration
from py3_tpcc.drivers.registry import get_driver_class, get_drivers
import py3_tpcc.drivers.spannerdriver  # noqa: F401
import py3_tpcc.drivers.sqlitedriver  # noqa: F401
from py3_tpcc.scaleparameters import ScaleParameters
from py3_tpcc.strategy import (
    DistributedExecutionStrategy,
    LocalExecutionStrategy,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s [%(funcName)s:%(lineno)03d] %(levelname)-5s: %(message)s"
    ),
    datefmt="%m-%d-%Y %H:%M:%S",
    stream=sys.stdout,
)

NOTIFY_PHASE_START_PATH = "/data/workdir/src/flamegraph/notify_phase_start.py"
NOTIFY_PHASE_END_PATH = "/data/workdir/src/flamegraph/notify_phase_end.py"


def notifyDSIOfPhaseStart(phasename: str) -> None:
    if os.path.isfile(NOTIFY_PHASE_START_PATH):
        output = subprocess.run(
            ["python3", NOTIFY_PHASE_START_PATH, phasename], capture_output=True
        )
        if output.returncode != 0:
            raise RuntimeError(
                "Failed to notify DSI of phase starting:", output
            )


def notifyDSIOfPhaseEnd(phasename: str) -> None:
    if os.path.isfile(NOTIFY_PHASE_END_PATH):
        output = subprocess.run(
            ["python3", NOTIFY_PHASE_END_PATH, phasename], capture_output=True
        )
        if output.returncode != 0:
            raise RuntimeError(
                "Failed to notify DSI of phase starting:", output
            )


def setup_argument_parser() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Python3 implementation of TPC-C Benchmark..."
    )

    # Dynamic choices for positional argument
    available_drivers = get_drivers()
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
        "--config",
        type=str,
        help="Path to the driver configuration file(format: toml).",
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
        metavar="SF",
        help="Benchmark scale factor. Default: 1",
    )

    parser.add_argument(
        "--samewh",
        default=85,
        type=float,
        metavar="PP",
        help="Percent paying same warehouse",
    )

    parser.add_argument(
        "--warehouses",
        default=4,
        type=int,
        metavar="W",
        help="Number of Warehouses to simulate. Default: 4",
    )

    parser.add_argument(
        "--starting-warehouse",
        default=None,
        type=int,
        metavar="SW",
        help="Starting warehouse ID for loading (optional, defaults to 1)",
    )
    parser.add_argument(
        "--ending-warehouse",
        default=None,
        type=int,
        metavar="EW",
        help="Ending warehouse ID for loading (optional, defaults to total warehouses)",
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
        default=os.path.realpath(
            os.path.join(os.path.dirname(__file__), "sql", "tpcc.sql")
        ),
        help="Path to the TPC-C DDL SQL file. Default: sql/tpcc.sql",
    )

    parser.add_argument(
        "--clients",
        type=int,
        default=1,
        metavar="N",
        help=(
            "The number of blocking clients (processes/nodes) to fork for "
            "parallel execution. Default: 1"
        ),
    )

    parser.add_argument(
        "--distributed",
        action="store_true",
        help=("Runs the benchmark in distributed mode using execnet."),
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

    return parser.parse_args()


async def main() -> None:

    args = setup_argument_parser()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    logger.info(f"Selected System: {args.system}")
    logger.info(f"Configuration: {args}")

    driverClass = get_driver_class(args.system)
    assert driverClass is not None, "Failed to find '%s' class" % args.system
    driver = driverClass(args.system, args.ddl)
    assert driver is not None, "Failed to create '%s' driver" % args.system

    # Load default configuration
    default_config = driver.make_default_config()

    # Load Config
    if args.config:
        logger.info(f"Loading configuration from {args.config}")
        driver.load_config(args.config)
    else:
        logger.info("Using default configuration")
        driver.load_config(default_config)

    # --print-config: Print Config and exit
    if args.print_config:
        driver.print_config()
        sys.exit(0)

    driver.connect()

    scale_parameters = ScaleParameters.makeWithScaleFactor(
        args.warehouses, args.scalefactor
    )
    logger.info(f"Scale Parameters: {scale_parameters}")

    # Override starting and ending warehouses if specified
    if args.starting_warehouse is not None:
        scale_parameters.starting_warehouse = args.starting_warehouse
        logging.info(
            "Using custom starting warehouse: %d", args.starting_warehouse
        )
    if args.ending_warehouse is not None:
        scale_parameters.ending_warehouse = args.ending_warehouse
        logging.info("Using custom ending warehouse: %d", args.ending_warehouse)

    # Validate warehouse range
    if scale_parameters.starting_warehouse > scale_parameters.ending_warehouse:
        logging.error(
            "Starting warehouse (%d) cannot be greater than ending warehouse (%d)",
            scale_parameters.starting_warehouse,
            scale_parameters.ending_warehouse,
        )
        sys.exit(1)

    actual_warehouses = (
        scale_parameters.ending_warehouse
        - scale_parameters.starting_warehouse
        + 1
    )

    logging.info(
        "Warehouse range for execution: %d to %d (total: %d warehouses)",
        scale_parameters.starting_warehouse,
        scale_parameters.ending_warehouse,
        actual_warehouses,
    )

    if args.distributed:
        strategy = DistributedExecutionStrategy(
            driver, args, driver.config, scale_parameters
        )
    else:
        strategy = LocalExecutionStrategy(
            driver, args, driver.config, scale_parameters
        )

    # Load Data
    load_time = None
    if not args.no_load:
        logging.info("Loading TPC-C benchmark data using %s" % (driver))
        notifyDSIOfPhaseStart("TPC-C_load")
        load_start = time.time()
        await strategy.load_data()
        load_time = time.time() - load_start
        notifyDSIOfPhaseEnd("TPC-C_load")

    # Execute Workload
    if not args.no_execute:
        notifyDSIOfPhaseStart("TPC-C_workload")
        results = await strategy.execute_workload()
        assert results, (
            "No results from execution for %d client!" % args.clients
        )
        notifyDSIOfPhaseEnd("TPC-C_workload")
        logging.info("Final Results")
        logging.info("Threads: %d", args.clients)
        logging.info(results.show(load_time, driver, args.clients, args.samewh))


if __name__ == "__main__":
    asyncio.run(main())
