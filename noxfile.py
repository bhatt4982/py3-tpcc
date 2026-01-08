"""Nox configuration for the project."""

import os

import nox

DEFAULT_PYTHON_VERSION = "3.13"

FLAKE8_VERSION = "flake8>=6.1.0,<7.3.0"
BLACK_VERSION = "black[jupyter]>=23.7.0,<25.11.0"
ISORT_VERSION = "isort>=5.11.0,<7.0.0"
LINT_PATHS = ["py3_tpcc", "tests", "noxfile.py"]

TEST_STANDARD_DEPENDENCIES = [
    "pytest",
]

# Error if a python version is missing
nox.options.error_on_missing_interpreters = True

nox.options.sessions = ["format", "lint", "unit", "integration"]

VERBOSE = True
MODE = "--verbose" if VERBOSE else "--quiet"


@nox.session(python=DEFAULT_PYTHON_VERSION)
def format(session):
    """
    Run isort to sort imports. Then run black
    to format code to uniform standard.
    """
    session.install(BLACK_VERSION, ISORT_VERSION)
    session.run(
        "isort",
        "--fss",
        *LINT_PATHS,
    )
    session.run(
        "black",
        "--line-length=80",
        *LINT_PATHS,
    )


@nox.session(python=DEFAULT_PYTHON_VERSION)
def lint(session):
    """Run linters.

    Returns a failure if the linters find linting errors or sufficiently
    serious code quality issues.
    """
    session.install(FLAKE8_VERSION)
    session.run(
        "flake8",
        "--max-line-length=80",
        *LINT_PATHS,
    )


@nox.session(python=DEFAULT_PYTHON_VERSION)
def unit(session):
    """Run unit tests."""
    session.install(*TEST_STANDARD_DEPENDENCIES)
    session.install("-e", ".")

    test_paths = (
        session.posargs if session.posargs else [os.path.join("tests", "unit")]
    )
    session.run(
        "py.test",
        MODE,
        f"--junitxml=unit_{session.python}_sponge_log.xml",
        *test_paths,
        env={},
    )


@nox.session(python=DEFAULT_PYTHON_VERSION)
def integration(session):
    """Run integration tests."""
    session.install(*TEST_STANDARD_DEPENDENCIES)
    session.install("-e", ".")

    test_paths = (
        session.posargs
        if session.posargs
        else [os.path.join("tests", "integration")]
    )
    session.run(
        "py.test",
        MODE,
        f"--junitxml=integration_{session.python}_sponge_log.xml",
        *test_paths,
        env={},
    )


@nox.session(python=DEFAULT_PYTHON_VERSION)
def build(session):
    """Build the package."""
    session.install("build", "setuptools", "wheel")
    session.run("python", "-m", "build", "--no-isolation")


@nox.session(python=DEFAULT_PYTHON_VERSION)
def install(session):
    """Install the package."""
    session.install("setuptools", "wheel")
    session.install(".", "--no-build-isolation")


@nox.session(python=DEFAULT_PYTHON_VERSION)
def run(session):
    """Run the driver."""
    session.install("setuptools", "wheel")
    session.install(".", "--no-build-isolation")
    session.run("python", "py3_tpcc/pytpcc.py", *session.posargs)
