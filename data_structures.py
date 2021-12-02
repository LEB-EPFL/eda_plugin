from dataclasses import dataclass


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
