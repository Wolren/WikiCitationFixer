"""
Logging setup for the wikifix pipeline.

Provides a ``--verbose`` / ``--quiet``-aware logger that replaces
bare ``print()`` calls throughout the codebase.
"""

import logging
import os
import sys

_LOGGER_NAME = "wikifix"


def setup_logger(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """Configure the root wikifix logger and return it.

    Args:
        verbose:  Log DEBUG messages (and above).
        quiet:    Only log WARNING messages (and above).

    Override with environment variable ``WIKIFIX_LOG_LEVEL``.
    """
    env_level = os.environ.get("WIKIFIX_LOG_LEVEL")
    if env_level:
        level: int = getattr(logging, env_level.upper(), logging.INFO)
    elif quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        if verbose or os.environ.get("WIKIFIX_LOG_LEVEL"):
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)-7s] %(message)s", datefmt="%H:%M:%S"
            )
        else:
            fmt = logging.Formatter("%(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    return logger


def get_logger() -> logging.Logger:
    """Return the existing wikifix logger, configuring a default one if needed."""
    return logging.getLogger(_LOGGER_NAME)
