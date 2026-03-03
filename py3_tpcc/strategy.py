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

    def __init__(self, driver_class, driver_args, config, scale_parameters):
        self.driver_class = driver_class
        self.args = driver_args
        self.config = config
        self.scale_parameters = scale_parameters

    @abstractmethod
    async def load_data(self) -> None:
        pass

    @abstractmethod
    async def execute_workload(self) -> Results:
        pass


class LocalExecutionStrategy(ExecutionStrategy):
    """
    Local multi-processing implementation ported from `pytpcc.py`.
    Initializes a localized thread pool to scale across multiple clients constraints.
    """

    def __init__(self, driver_class, driver_args, config, scale_parameters):
        super().__init__(driver_class, driver_args, config, scale_parameters)
        # Instantiate primary driver for the local process
        self.driver = self.driver_class(self.args.system, self.args.ddl)
        self.driver.load_config(self.config)

    async def load_data(self) -> None:
        assert self.driver is not None
        logging.debug(
            f"Creating local client pool with {self.args.clients} processes"
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

    @staticmethod
    def _loader_func(driver, scale_parameters, args, w_ids):
        logging.debug(
            f"Starting client execution: {driver} [warehouses={len(w_ids)}]"
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
            logging.warn(f"Failed to load data: {ex}")
            traceback.print_exc(file=sys.stdout)
            raise

    async def execute_workload(self) -> Results:
        assert self.driver is not None
        tasks = [
            LocalExecutionStrategy._executor_func(
                self.driver, self.args, self.scale_parameters
            )
            for _ in range(self.args.clients)
        ]
        worker_results = await asyncio.gather(*tasks)
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
        return results


class DistributedExecutionStrategy(ExecutionStrategy):
    """
    Distributed ssh-network implementation ported from `coordinator.py`.
    Initializes execnet gateways to dispatch processing instructions across remote clients.
    """

    def __init__(self, driver_class, driver_args, config, scale_parameters):
        super().__init__(driver_class, driver_args, config, scale_parameters)

        assert (
            execnet is not None
        ), "DistributedExecutionStrategy requires the 'execnet' module but it is missing. Run `pip install execnet`."
        self.channels = []
        assert (
            config.get("clients", "") != ""
        ), "No clients specified in config for distributed execution"

        remote_clients = re.split(r"\s+", str(config["clients"]))

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
            self.channels[i].send(pickle.dumps(m, -1))

        for ch in self.channels:
            ch.receive()

    async def execute_workload(self) -> Results:
        total_results = Results()

        for ch in self.channels:
            m = message.Message(
                header=message.CMD_EXECUTE,
                data=[self.scale_parameters, vars(self.args), self.config],
            )
            ch.send(pickle.dumps(m, -1))

        for ch in self.channels:
            r = pickle.loads(ch.receive()).data
            total_results.append(r)

        return total_results
