#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import asyncio
import logging
import multiprocessing
import os
import subprocess
import sys
import time
import traceback

from py3_tpcc.results import Results
from py3_tpcc.runtime.executor import Executor
from py3_tpcc.runtime.loader import Loader
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

NOTIFY_PHASE_START_PATH = "/data/workdir/src/flamegraph/notify_phase_start.py"
NOTIFY_PHASE_END_PATH = "/data/workdir/src/flamegraph/notify_phase_end.py"


def notifyDSIOfPhaseStart(phasename):
    if os.path.isfile(NOTIFY_PHASE_START_PATH):
        output = subprocess.run(
            ["python3", NOTIFY_PHASE_START_PATH, phasename], capture_output=True
        )
        if output.returncode != 0:
            raise RuntimeError(
                "Failed to notify DSI of phase starting:", output
            )


def notifyDSIOfPhaseEnd(phasename):
    if os.path.isfile(NOTIFY_PHASE_END_PATH):
        output = subprocess.run(
            ["python3", NOTIFY_PHASE_END_PATH, phasename], capture_output=True
        )
        if output.returncode != 0:
            raise RuntimeError(
                "Failed to notify DSI of phase starting:", output
            )


def setup_argument_parser():
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
            os.path.join(os.path.dirname(__file__), "tpcc.sql")
        ),
        help="Path to the TPC-C DDL SQL file. Default: tpcc.sql",
    )

    parser.add_argument(
        "--clients",
        type=int,
        default=1,
        metavar="N",
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


async def load_data(driver, args, scale_parameters):
    assert driver is not None
    logging.debug("Creating client pool with %d processes" % args.clients)
    pool = multiprocessing.Pool(args.clients)

    # Split the warehouses into chunks
    w_ids = [[] for _ in range(args.clients)]
    for w_id in range(
        scale_parameters.starting_warehouse,
        scale_parameters.ending_warehouse + 1,
    ):
        idx = w_id % args.clients
        w_ids[idx].append(w_id)

    loader_results = []
    for i in range(args.clients):
        r = pool.apply_async(
            _loader_func, (driver, scale_parameters, args, w_ids[i])
        )
        loader_results.append(r)

    pool.close()
    logging.debug("Waiting for %d loaders to finish" % args.clients)
    pool.join()


def _loader_func(driver, scale_parameters, args, w_ids):
    logging.debug(
        "Starting client execution: %s [warehouses=%d]" % (driver, len(w_ids))
    )
    try:
        need_load_items = 1 in w_ids
        loader = Loader(driver, scale_parameters, w_ids, need_load_items)
        driver.load_start()
        loader.load()
        driver.load_end()
    except KeyboardInterrupt:
        return -1
    except (Exception, AssertionError) as ex:
        logging.warn("Failed to load data: %s" % (ex))
        traceback.print_exc(file=sys.stdout)
        raise


async def execute_workload(driver, args, scale_parameters) -> Results:
    assert driver is not None
    tasks = [
        _executor_func(driver, args, scale_parameters)
        for _ in range(args.clients)
    ]
    await asyncio.gather(*tasks)
    return Results()


async def _executor_func(driver, args, scale_parameters):
    logging.debug("Starting client execution: %s" % driver)
    e = Executor(driver, scale_parameters, stop_on_error=args.stop_on_error)
    driver.execute_start()
    results = e.run(args.duration)
    driver.execute_end()
    return results


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

    # Load Data
    load_time = None
    if not args.no_load:
        logging.info("Loading TPC-C benchmark data using %s" % (driver))
        notifyDSIOfPhaseStart("TPC-C_load")
        load_start = time.time()
        await load_data(driver, args, scale_parameters)
        load_time = time.time() - load_start
        notifyDSIOfPhaseEnd("TPC-C_load")

    # Execute Workload
    if not args.no_execute:
        notifyDSIOfPhaseStart("TPC-C_workload")
        results = await execute_workload(driver, args, scale_parameters)
        assert results, (
            "No results from execution for %d client!" % args.clients
        )
        notifyDSIOfPhaseEnd("TPC-C_workload")
        logging.info("Final Results")
        logging.info("Threads: %d", args.clients)
        logging.info(results.show(load_time, driver, args.clients, args.samewh))


if __name__ == "__main__":
    asyncio.run(main())
