"""Shared logging configuration for the hockey analytics pipeline."""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger that writes to stdout.

    Safe to call multiple times for the same name -- handlers are only
    attached once per logger instance, so repeated calls (e.g. importing
    a module twice) never duplicate log lines.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
