"""Utility for the settings file."""

import json
import logging

def get_settings(calling_class=None):
    """Get the settings from the settings.json file and extract a module if defined."""
    with open("settings.json", "r") as j:
        contents = json.loads(j.read())
    if calling_class is None:
        return contents
    else:
        trace = calling_class.__class__.__module__.split('.')
        for module in trace:
            contents = contents[module]
        return contents

def setup_logging():
    logger = logging.getLogger("EDA")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)