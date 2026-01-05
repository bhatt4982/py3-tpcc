# py3-tpcc

Python TPC-C Compliance Test Suite.

## Installation

```bash
pip install py3-tpcc
```

## Development

This project uses [nox](https://nox.thea.codes/en/stable/) for task automation.

### Prerequisites

- Python 3.10+
- `nox`

### Running Tests

Run unit tests:
```bash
nox -s unit
```

Run integration tests:
```bash
nox -s integration
```

### Linting & Formatting

Check code quality:
```bash
nox -s lint
```

Format code:
```bash
nox -s format
```

## License

Apache-2.0