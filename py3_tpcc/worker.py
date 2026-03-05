#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
# Copyright (C) 2011
# Andy Pavlo & Yang Lu
# http:#www.cs.brown.edu/~pavlo/
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
Distributed Remote Worker

Entry point for remote nodes deployed via `execnet` to act as distributed
data loaders or workload executors. It listens to a communication channel
for serialized commands from the coordinator and dispatches `Loader` or
`Executor` tasks before pushing results back across the IPC channel.
"""

import logging
import pickle
import sys
import traceback

import py3_tpcc.message as message
from py3_tpcc.runtime import executor, loader

channel = globals().get("channel")  # noqa: F821


# createDriverClass
def createDriverClass(name):
    """
    Dynamically loads and instantiates the proper database driver class
    based on the name provided in the execution config.
    """
    full_name = "%sDriver" % name.title()
    mod = __import__(
        "drivers.%s" % full_name.lower(), globals(), locals(), [full_name]
    )
    klass = getattr(mod, full_name)
    return klass


# loaderFunc
def loaderFunc(driverClass, scaleParameters, args, config, w_ids, debug):
    """
    Instantiates the target driver and executes the Data Loader logic to 
    initialize the assigned warehouses for this specific worker node.
    """
    driver = driverClass(args["system"], args["ddl"])
    assert driver is not None
    logging.debug(
        "Starting client execution: %s [warehouses=%d]" % (driver, len(w_ids))
    )

    config["load"] = True
    config["execute"] = False
    config["reset"] = False
    driver.load_config(config)

    try:
        load_items = 1 in w_ids
        loader_instance = loader.Loader(
            driver, scaleParameters, w_ids, load_items
        )
        driver.load_start()
        loader_instance.execute()
        driver.load_end()
    except KeyboardInterrupt:
        return -1
    except (Exception, AssertionError) as ex:
        logging.warn("Failed to load data: %s" % (ex))
        # if debug:
        traceback.print_exc(file=sys.stdout)
        raise


# executorFunc
def executorFunc(driverClass, scaleParameters, args, config, debug):
    """
    Instantiates the driver and connects the `Executor` to run a block
    of runtime transactions before concluding.
    """
    driver = driverClass(args["system"], args["ddl"])
    assert driver is not None
    logging.debug("Starting client execution: %s" % driver)

    config["execute"] = True
    config["reset"] = False
    driver.load_config(config)

    e = executor.Executor(
        driver,
        scaleParameters,
        stop_on_error=args["stop_on_error"],
        sameWH=args["samewh"],
    )
    driver.execute_start()
    results = e.execute(args["duration"])
    driver.execute_end()

    return results


# MAIN
if __name__ == "__channelexec__":
    driverClass = None
    for item in channel:
        command = pickle.loads(item)
        if command.header == message.CMD_LOAD:
            scaleParameters = command.data[0]
            args = command.data[1]
            config = command.data[2]
            w_ids = command.data[3]

            # Create a handle to the target client driver at the client side
            driverClass = createDriverClass(args["system"])
            assert driverClass is not None, (
                "Failed to find '%s' class" % args["system"]
            )
            driver = driverClass(args["system"], args["ddl"])
            assert driver is not None, (
                "Failed to create '%s' driver" % args["system"]
            )

            loaderFunc(driverClass, scaleParameters, args, config, w_ids, True)
            m = message.Message(header=message.LOAD_COMPLETED)
            channel.send(pickle.dumps(m, -1))
        elif command.header == message.CMD_EXECUTE:
            scaleParameters = command.data[0]
            args = command.data[1]
            config = command.data[2]

            # Create a handle to the target client driver at the client side
            if driverClass is None:
                driverClass = createDriverClass(args["system"])
                assert driverClass is not None, (
                    "Failed to find '%s' class" % args["system"]
                )
                driver = driverClass(args["system"], args["ddl"])
                assert driver is not None, (
                    "Failed to create '%s' driver" % args["system"]
                )

            results = executorFunc(
                driverClass, scaleParameters, args, config, True
            )
            m = message.Message(header=message.EXECUTE_COMPLETED, data=results)
            channel.send(pickle.dumps(m, -1))

        elif command.header == message.CMD_STOP:
            pass
        else:
            pass
