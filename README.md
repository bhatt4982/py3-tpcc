# py3-tpcc: Python 3 TPC-C Benchmark

## Overview

py3-tpcc is a Python 3 compatible implementation of the TPC-C benchmark. Approved in July 1992, TPC Benchmark C is a complex on-line transaction processing (OLTP) benchmark that involves a mix of five concurrent transactions of different types and complexity. The database is comprised of nine types of tables. TPC-C is measured in transactions per minute (tpmC).

This repository is a modern Python 3 port that combines the base architecture of the original py-tpcc with advanced driver implementations.

## Architecture & Custom Drivers

The basic idea behind this framework is that you create a driver file for your specific database system that implements the functions defined in abstractdriver.py. All the heavy lifting for generating the tuples and the input parameters for the transactions has already been done for you.

### To get started with a new system:

* Create a new file in the drivers directory (e.g., mongodbdriver.py) that contains a class matching your system's name (e.g., MongodbDriver).
* Implement a function to load the tuples into your database for a given table.
* Implement the five separate functions that execute the TPC-C transactions based on the provided input parameters.
* Define the configuration file parameters that are returned by the makeDefaultConfig function in your driver.

**Tip**: You can look at the SpannerDriver implementations to get an idea of what your transaction functions need to do.

## Setup & Installation

Create and activate a Python 3 virtual environment:

```shell
python3 -m virtualenv .venv
source .venv/bin/activate
```

Install the package and its dependencies:

```shell
pip install -e .
```

Install any database-specific dependencies (e.g., for Spanner or PostgreSQL):

```shell
pip install python-mydatabase-driver
```

## Usage

1. Generate a Configuration File
You can print out the driver's default configuration dictionary to a file using the --print-config flag:

```shell
# For mydatabase
python3 py3_tpcc/pytpcc.py --print-config mydatabase > mydatabase.config

# For spanner
python3 py3_tpcc/pytpcc.py --print-config spanner > spanner.config
```

2. Run the Benchmark

You can control the execution phases using various flags:

* Only Load Data: Test the data loader first without executing transactions.

```shell
python3 py3_tpcc/pytpcc.py --no-execute --clients=100 --duration=10 --warehouses=21 --config=mydatabase.config mydatabase --stop-on-error
```

* Execute Tests (No Load): Use data that is already populated in the database.

```shell
python3 py3_tpcc/pytpcc.py --no-load --clients=100 --duration=10 --warehouses=21 --config=mydatabase.config mydatabase --stop-on-error
```

* Full Run (Reset, Load, and Execute):

```shell
python3 py3_tpcc/pytpcc.py --reset --clients=100 --duration=10 --warehouses=21 --config=mydatabase.config mydatabase --stop-on-error
```

(**Note**: For relational SQL drivers like PostgreSQL or GoogleSQL, you may also need to pass the `--ddl` flag with the appropriate schema file, e.g., `--ddl py3_tpcc/sql/tpcc_googlesql.sql` for Spanner)

3. Debugging

The CSV driver is highly useful if you want to see what the generated data or transaction input parameters look like. You can dump the inputs directly to files in /tmp/tpcc-*:

```shell
python3 py3_tpcc/pytpcc.py csv
```

### Distributed / Multi-Node Execution

For large-scale testing, this project includes a distributed runner. It uses `pytpcc.py` as the unified entry point.

* Pass the `--distributed` flag to switch into distributed execution mode.
* The `--clients` argument specifies how many worker processes should run on each client node. Example:

```shell
python3 py3_tpcc/pytpcc.py --config mydatabase.config --distributed --clients 5 mydatabase
```

* All client node addresses/IPs and their respective code directories must be specified in your configuration file.

* Dependency: Distributed execution requires the `execnet` Python module to be installed on each client (`pip install execnet`).

## Development

This project uses [nox](https://nox.thea.codes/en/stable/) for task automation.

### Prerequisites

- Python 3.10+
- `nox`

### Running Tests

Run unit tests:

```shell
nox -s unit
```

Run integration tests:

```shell
nox -s integration
```

### Linting & Formatting

Check code quality:

```shell
nox -s lint
```

Format code:

```shell
nox -s format
```

## License

Apache-2.0
