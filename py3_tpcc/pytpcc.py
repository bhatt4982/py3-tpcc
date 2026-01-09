#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import asyncio
import logging
import multiprocessing
import os
import sys
import time

from py3_tpcc.results import Results
from py3_tpcc.scaleparameters import ScaleParameters

# Ensure we can import py3_tpcc when running as a script
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to trigger registration
from py3_tpcc.drivers.registry import get_driver_class, get_drivers
import py3_tpcc.drivers.spannerdriver  # noqa: F401
import py3_tpcc.drivers.sqlitedriver  # noqa: F401

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s [%(funcName)s:%(lineno)03d] %(levelname)-5s: %(message)s"
    ),
    datefmt="%m-%d-%Y %H:%M:%S",
    stream=sys.stdout,
)


def setup_argument_parser():
    parser = argparse.ArgumentParser(
        description="Python TPC-C Benchmark Driver"
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

    return parser.parse_args()


def create_driver_class(name):
    full_name = "%sDriver" % name.title()
    mod = __import__(
        "drivers.%s" % full_name.lower(), globals(), locals(), [full_name]
    )
    klass = getattr(mod, full_name)
    return klass


async def _load():
    pass


async def load_data(driver, args, scale_parameters):
    logging.debug("Creating client pool with %d processes" % args.clients)
    pool = multiprocessing.Pool(args.clients)
    # debug = logging.getLogger().isEnabledFor(logging.DEBUG)

    loader_results = []
    for i in range(args.clients):
        r = pool.apply_async(_load)
        loader_results.append(r)

    pool.close()
    logging.debug("Waiting for %d loaders to finish" % args.clients)
    pool.join()


async def _execute():
    pass


async def execute_workload(driver, args, scale_parameters) -> Results:
    tasks = [_execute() for _ in range(args.clients)]
    await asyncio.gather(*tasks)
    return Results()


def print_config(driver):
    print(driver.format_config(driver.config))
    print()


async def main():

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
    driver.make_default_config()

    # Load Config
    if args.config:
        logger.info(f"Loading configuration from {args.config}")
        driver.load_config(args.config)

    # --print-config: Print Config and exit
    if args.print_config:
        print_config(driver)
        sys.exit(0)

    scale_parameters = ScaleParameters.makeWithScaleFactor(
        args.warehouses, args.scalefactor
    )
    # Load Data
    load_time = None
    if not args.no_load:
        logging.info("Loading TPC-C benchmark data using %s" % (driver))
        load_start = time.time()
        await load_data(driver, args, scale_parameters)
        load_time = time.time() - load_start

    # Execute Workload
    if not args.no_execute:
        results = await execute_workload(driver, args, scale_parameters)
        assert results
        print(results.show(load_time))


if __name__ == "__main__":
    asyncio.run(main())
