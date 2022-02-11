"""Dataclassed used to bundle information."""


from dataclasses import dataclass
import numpy as np
import logging

# MMSettings
from dataclasses import dataclass
from typing import List, Any
from pathlib import Path


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


@dataclass
class MMChannel:
    """Part of a channel as found in the MDA channels list in MM."""

    name: str
    active: bool
    power: float
    exposure_ms: int


@dataclass
class MMSettings:
    """Settings mainly as in MM, but some things are iSIM specific.

    Sweeps_per_frame: How many times does the galvo go back and forth during one exposure. Can be
    bigger for longer exposure times, to reduce the time a specific part is exposed to light, to
    reduce phototoxicity.
    """

    java_settings: Any = None

    timepoints: int = 11
    interval_ms: int = 1000

    pre_delay: float = 0.0
    post_delay: float = 0.03

    java_channels: Any = None
    use_channels = True
    channels: List[MMChannel] = None
    n_channels: int = 0

    slices_start: float = None
    slices_end: float = None
    slices_step: float = None
    slices: List[float] = None
    n_slices: int = None
    use_slices: bool = False

    save_path: Path = None
    prefix: str = None

    sweeps_per_frame: int = 1

    acq_order: str = None

    def __post_init__(self):
        """Take the settings from MM as a java object and get the settings are represented here.

        Function that is called after parameters above are initialized by the dataclass.
        """
        if self.java_settings is not None:
            # print(dir(self.java_settings))
            self.interval_ms = self.java_settings.interval_ms()
            self.timepoints = self.java_settings.num_frames()
            self.java_channels = self.java_settings.channels()
            self.acq_order = self.java_settings.acq_order_mode()
            self.use_channels = self.java_settings.use_channels()

        try:
            self.java_channels.size()
        except:
            return

        self.channels = {}
        self.n_channels = 0
        for channel_ind in range(self.java_channels.size()):
            channel = self.java_channels.get(channel_ind)
            config = channel.config()
            self.channels[config] = {
                "name": config,
                "use": channel.use_channel(),
                "exposure": channel.exposure(),
                "z_stack": channel.do_z_stack(),
            }
            if self.channels[config]["use"]:
                self.n_channels += 1

        self.use_slices = self.java_settings.use_slices()
        self.java_slices = self.java_settings.slices()
        self.slices = []
        for slice_num in range(self.java_settings.slices().size()):
            self.slices.append(self.java_slices.get(slice_num))
        if len(self.slices) == 0:
            self.slices = [0]
        self.n_slices = len(self.slices)
