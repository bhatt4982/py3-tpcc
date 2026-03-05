"""
Execution Strategy Orchestration

Defines the interfaces and orchestration models for dispatching execution
commands (data loading and transaction running) locally across subprocesses
or via distributed agent execution using `execnet` and SSH channels.
"""

try:
    import execnet
except ImportError:
    execnet = None
from abc import ABC, abstractmethod
import asyncio
import logging
import multiprocessing
import pickle
import re
import sys
import traceback

from py3_tpcc import message, worker
from py3_tpcc.results import Results
from py3_tpcc.runtime.executor import Executor
from py3_tpcc.runtime.loader import Loader


class ExecutionStrategy(ABC):
    """
    Abstract interface for handling TPC-C data loading and workload execution.
    Subclasses will implement these routines via either a localized processing pool
    or distributed remote agent execution.
    """

    def __init__(self, driver, driver_args, config, scale_parameters):
        """
        Initializes the base execution strategy state.

        Args:
            driver: The instantiated driver class tailored to the specific SQL database backend.
            driver_args (argparse.Namespace): Arguments passed from the invocation script.
            config (dict): The resolved configuration parameters mapped from driver initialization.
            scale_parameters (ScaleParameters): Evaluated scaling rules. 
        """
        self.driver = driver
        self.args = driver_args
        self.config = config
        self.scale_parameters = scale_parameters

    @abstractmethod
    async def load_data(self) -> None:
        """
        Signals underlying worker instances (local or distributed) to invoke DataLoader creation routines.
        """
        pass

    @abstractmethod
    async def execute_workload(self) -> Results:
        """
        Signals underlying worker instances to invoke Executor transactions and return unified results.
        
        Returns:
            Results: Single collected structure detailing the sum transactions across all nodes.
        """
        pass


class LocalExecutionStrategy(ExecutionStrategy):
    """
    Local multi-processing implementation ported from `pytpcc.py`.
    Initializes a localized thread pool to scale across multiple clients constraints.
    """

    def __init__(self, driver, driver_args, config, scale_parameters):
        super().__init__(driver, driver_args, config, scale_parameters)

    async def load_data(self) -> None:
        assert self.driver is not None
        logging.info(
            f"Starting local data load with {self.args.clients} processes"
        )
        pool = multiprocessing.Pool(self.args.clients)

        # Split the warehouses into chunks
        w_ids = [[] for _ in range(self.args.clients)]
        for w_id in range(
            self.scale_parameters.starting_warehouse,
            self.scale_parameters.ending_warehouse + 1,
        ):
            idx = w_id % self.args.clients
            w_ids[idx].append(w_id)

        loader_results = []
        for i in range(self.args.clients):
            r = pool.apply_async(
                LocalExecutionStrategy._loader_func,
                (self.driver, self.scale_parameters, self.args, w_ids[i]),
            )
            loader_results.append(r)

        pool.close()
        logging.debug(
            f"Waiting for {self.args.clients} local loaders to finish"
        )
        pool.join()
        logging.info("Local data load completed")

    @staticmethod
    def _loader_func(driver, scale_parameters, args, w_ids):
        logging.debug(
            f"Starting client execution: {driver} [warehouses={len(w_ids)}]"
        )
        try:
            need_load_items = 1 in w_ids
            loader = Loader(driver, scale_parameters, w_ids, need_load_items)
            driver.load_start()
            loader.execute()
            driver.load_end()
            logging.debug(f"Completed client execution for warehouses: {w_ids}")
        except KeyboardInterrupt:
            return -1
        except (Exception, AssertionError) as ex:
            logging.warn(f"Failed to load data: {ex}")
            traceback.print_exc(file=sys.stdout)
            raise

    async def execute_workload(self) -> Results:
        assert self.driver is not None
        logging.info(f"Executing local workload with {self.args.clients} clients")
        tasks = [
            LocalExecutionStrategy._executor_func(
                self.driver, self.args, self.scale_parameters
            )
            for _ in range(self.args.clients)
        ]
        worker_results = await asyncio.gather(*tasks)
        logging.debug("All worker tasks completed")
        total_results = Results()
        for r in worker_results:
            total_results.append(r)
        return total_results

    @staticmethod
    async def _executor_func(driver, args, scale_parameters):
        logging.debug(f"Starting local client execution: {driver}")
        e = Executor(driver, scale_parameters, stop_on_error=args.stop_on_error)
        driver.execute_start()
        results = e.execute(args.duration)
        driver.execute_end()
        logging.debug(f"Finished local client execution: {driver}")
        return results


class DistributedExecutionStrategy(ExecutionStrategy):
    """
    Distributed ssh-network implementation ported from `coordinator.py`.
    Initializes execnet gateways to dispatch processing instructions across remote clients.
    """

    def __init__(self, driver, driver_args, config, scale_parameters):
        super().__init__(driver, driver_args, config, scale_parameters)

        assert (
            execnet is not None
        ), "DistributedExecutionStrategy requires the 'execnet' module but it is missing. Run `pip install execnet`."
        self.channels = []
        assert (
            config.get("clients", "") != ""
        ), "No clients specified in config for distributed execution"

        remote_clients = re.split(r"\s+", str(config["clients"]))
        logging.info(f"Creating distributed execution strategy across nodes: {remote_clients}")

        # Create ssh channels to client nodes
        for node in remote_clients:
            cmd = "ssh=" + node + r"//chdir=" + config.get("path", "")
            for i in range(self.args.clients):
                gw = execnet.makegateway(cmd)
                ch = gw.remote_exec(worker)
                self.channels.append(ch)

    async def load_data(self) -> None:
        procs = len(self.channels)
        w_ids = [[] for _ in range(procs)]

        for w_id in range(
            self.scale_parameters.starting_warehouse,
            self.scale_parameters.ending_warehouse + 1,
        ):
            idx = w_id % procs
            w_ids[idx].append(w_id)

        logging.info(
            f"Distributing load parameters across {procs} channels: {w_ids}"
        )

        for i in range(len(self.channels)):
            m = message.Message(
                header=message.CMD_LOAD,
                data=[
                    self.scale_parameters,
                    vars(self.args),
                    self.config,
                    w_ids[i],
                ],
            )
            logging.debug(f"Sending LOAD command to channel {i}")
            self.channels[i].send(pickle.dumps(m, -1))

        logging.debug("Waiting for remote loads to complete")
        for ch in self.channels:
            ch.receive()
            
        logging.info("Distributed data load completed")

    async def execute_workload(self) -> Results:
        total_results = Results()
        logging.info(f"Executing distributed workload across {len(self.channels)} channels")

        for ch in self.channels:
            m = message.Message(
                header=message.CMD_EXECUTE,
                data=[self.scale_parameters, vars(self.args), self.config],
            )
            ch.send(pickle.dumps(m, -1))

        for ch in self.channels:
            r = pickle.loads(ch.receive()).data
            total_results.append(r)
            
        logging.debug("Received all distributed workload results")

        return total_results
