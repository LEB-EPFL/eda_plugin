"""Dataclassed used to bundle information."""


from dataclasses import dataclass
import numpy as np
import logging

log = logging.getLogger("EDA")


@dataclass
class EDAEvent:
    """Event that is detected by an imageanalyser to be interpreted by an interpreter."""

    probability: float
    position: tuple
    time: int
    timepoint: int


@dataclass
class ParameterSet:
    """Set of parameters for the BinaryFrameRateInterpreter."""

    slow_interval: float
    fast_interval: float
    lower_threshold: int
    upper_threshold: int

    def __init__(self, *args, **params: dict):
        """If parameters were passed in as a dict, translate."""
        log.info(f"{args} {len(args)}")

        if len(params.items()) > 0:
            log.info(params)
            self.slow_interval = params["slow_interval"]
            self.fast_interval = params["fast_interval"]
            self.lower_threshold = params["lower_threshold"]
            self.upper_threshold = params["upper_threshold"]

        if len(args) > 0:
            self.slow_interval = args[0]["slow_interval"]
            self.fast_interval = args[0]["fast_interval"]
            self.lower_threshold = args[0]["lower_threshold"]
            self.upper_threshold = args[0]["upper_threshold"]


@dataclass
class PyImage:
    """Image as a standard ndarray with very basic metadata attached."""

    raw_image: np.ndarray
    timepoint: int
    channel: int
    z_slice: int
    time: int
