# Justification for using asyncio specifically for the Executor/Client phase of this project.

## 1. TPC-C is I/O Bound, Not CPU Bound

The primary job of the TPC-C client (implemented in pytpcc/runtime/executor.py) is not to perform complex calculations, but to wait for the database.

**The Workflo**w: The client generates a few random numbers (CPU), sends a request to the database (Network I/O), and waits for the response.

**The Reality**: In a typical benchmark, the network latency and database processing time (e.g., waiting for a write lock in MongoDB or a COMMIT in SQLite) consume 90-99% of the transaction time.

**Why Asyncio Wins**: While one client is awaiting a response from the DB, asyncio immediately yields the CPU to the next client. The GIL is released during these I/O operations, meaning the "single process" limit is never hit because the CPU is mostly idle waiting for the network anyway.

## 2. Scalability: Coroutines vs. Processes

Multiprocessing is for "high throughput," but multiprocessing actually creates a hard ceiling on the number of clients you can simulate.

**Current Model**: Multiprocessing requires 1 OS Process per Client.

**Overhead**: If you want to simulate 1,000 concurrent users (a standard TPC-C requirement), you need 1,000 OS processes. This consumes massive amounts of RAM (e.g., 20MB \* 1000 = 20GB) and forces the OS to context-switch heavily.

**Result**: You will likely run out of memory or hit OS process limits before you saturate a high-performance database.

## Asyncio (Proposed Model):

Requires 1 Coroutine per Client.

**Overhead**: A Python coroutine costs bytes of memory. You can easily run 10,000+ concurrent clients on a single CPU core.

**Result**: You can generate massively higher concurrency from a single laptop, stressing the database (the goal of the benchmark) rather than the benchmark tool.

## 3. Evidence from the Code

**Look at pytpcc/drivers/sqlitedriver.py**: The doPayment function performs almost no logic. It constructs a query and calls self.cursor.execute(). This call blocks until SQLite writes to disk.

In **Multiprocessing**: The entire CPU core sits idle while the disk spins.

In **Asyncio**: The event loop marks this task as "waiting" and runs the next client's transaction immediately.

## 4. The Nuance: Where Multiprocessing IS Correct

You should concede that Data Loading (loader.py) is effectively CPU-bound.

Generating millions of random strings (nurand.py) to populate the database initially is heavy on the CPU.

**Strategy**: Keep multiprocessing for the Loader (to utilize all cores for data generation), but switch to asyncio for the Executor (workload simulation).

## Summary:

We chose asyncio for the execution phase because the TPC-C workload is heavily I/O bound (waiting on DB responses). The bottleneck is network latency, not CPU cycles. multiprocessing introduces significant memory overhead per client, limiting our ability to simulate the thousands of concurrent connections required for a realistic benchmark. asyncio allows us to saturate the database connection pool from a single node with minimal resource overhead.
