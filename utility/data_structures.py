from dataclasses import dataclass
import numpy as np

@dataclass
class EDAEvent:
    probability: float
    position: tuple
    time: int
    timepoint: int


@dataclass
class ParameterSet:
    slow_interval: float
    fast_interval: float
    lower_threshold: int
    upper_threshold: int

@dataclass
class PyImage:
    raw_image: np.ndarray
    timepoint: int
    channel: int
    z_slice: int
    time: int
