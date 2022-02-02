"""Dataclassed used to bundle information."""


from dataclasses import dataclass
import numpy as np


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


@dataclass
class PyImage:
    """Image as a standard ndarray with very basic metadata attached."""

    raw_image: np.ndarray
    timepoint: int
    channel: int
    z_slice: int
    time: int
