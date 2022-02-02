"""Example of using the PycroAcquisition class."""

import time
import numpy as np
from actuators.pycromanager import PycroAcquisition
import tifffile
import logging

log = logging.getLogger("EDA")


class InjectedPycroAcquisition(PycroAcquisition):
    """Acquisition based on pycromanager with image injection.

    This can be used with the DemoConfig of MicroManager. It injects an image from a tif-stack to
    replace the image from the DemoCam. This allows to test the performance of the EDA loop and the
    model used without a sample or even a microscope.
    """

    def __init__(self, *args, **kwargs):
        """Make a short starting sequence and load the tif file into memory."""
        my_settings = {
            "num_time_points": 10,
            "time_interval_s": 1,
            "channel_group": "Channel",
            "channels": ["FITC", "DAPI"],
            "order": "tc",
        }
        super().__init__(*args, settings=my_settings, **kwargs)
        tif_file = "C:/Users/stepp/Documents/02_Raw/SmartMito/180420_120_comp.tif"
        self.frame_time = 0.15  # s
        self.tif = tifffile.imread(tif_file)
        self.start_time = time.perf_counter()
        self.timepoint = 0
        log.info(f"{tif_file} loaded with shape {self.tif.shape}")

    def receive_image(self, image, metadata):
        """Overwrite the function in the original PycroAcquisition.

        Add the image replacement before calling the original function on the injected image. The
        frame is chosen from the tif stack according to the time passed since the last acquired
        frame.
        """
        for idx, c in enumerate(self.channels):
            if metadata["Channel"] == c["config"]:
                channel = idx

        if channel == 0:
            now = time.perf_counter()
            elapsed = now - self.start_time
            timepoint = round(elapsed / self.frame_time)
            timepoint = np.max([timepoint, self.timepoint + 1])
            self.timepoint = np.mod(timepoint, self.tif.shape[0])

        image = self.tif[self.timepoint, channel, :, :]
        # Send this image to the main receive_image function of PycroAcquisition
        return super().receive_image(image, metadata)
