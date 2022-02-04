"""Utility for the settings file. And other module wide settings."""

import json
import logging
import os


def get_settings(calling_class=None):
    """Get the settings from the settings.json file and extract a module if defined."""
    with open(os.path.dirname(__file__) + "/../settings.json", "r") as j:
        contents = json.loads(j.read())
    if calling_class is None:
        return contents
    else:
        trace = calling_class.__module__.split(".")
        for module in trace:
            contents = contents[module]
        return contents


def setup_logging():
    """Set up the logging for the project."""
    logger = logging.getLogger("EDA")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
