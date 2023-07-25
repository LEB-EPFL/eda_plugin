"""Example of using the PycroAcquisition class."""

import logging
import time

from qtpy.QtWidgets import QFileDialog
import numpy as np
import tifffile
from eda_plugin.actuators.pycromanager import PycroAcquisition

log = logging.getLogger("EDA")


class InjectedPycroAcquisition(PycroAcquisition):
    """Acquisition based on pycromanager with image injection.

    This can be used with the DemoConfig of MicroManager. It injects an image from a tif-stack to
    replace the image from the DemoCam. This allows to test the performance of the EDA loop and the
    model used without a sample or even a microscope.
    """

    def __init__(self, *args, **kwargs):
        """Make a short starting sequence and load the tif file into memory."""

        super().__init__(*args, **kwargs)
        tif_file = "/data/small.tif"
        try:
            self.tif = tifffile.imread(tif_file)
        except FileNotFoundError:
            tif_file = QFileDialog.getOpenFileName(caption="Choose TIF file")
            print(tif_file)
            self.tif = tifffile.imread(tif_file[0])
        self.tif = self.tif.astype(np.uint16)
        self.frame_time = 0.15  # s
        self.start_time = time.perf_counter()
        self.timepoint = 0
        log.info(f"{tif_file} loaded with shape {self.tif.shape}")

    def receive_image(self, image: np.ndarray, metadata):
        """Overwrite the function in the original PycroAcquisition.

        Add the image replacement before calling the original function on the injected image. The
        frame is chosen from the tif stack according to the time passed since the last acquired
        frame.
        """
        for idx, c in enumerate(self.channels):
            if metadata["Channel"] == c:
                channel = idx

        # log.debug(metadata)

        if channel == 0:
            now = time.perf_counter()
            elapsed = now - self.start_time
            timepoint = round(elapsed / self.frame_time)
            timepoint = np.max([timepoint, self.timepoint + 1])
            self.timepoint = np.mod(timepoint, self.tif.shape[0])

        image = self.tif[self.timepoint, channel, :, :]
        log.debug(f"Injected image: {image.shape}")
        # Send this image to the main receive_image function of PycroAcquisition
        return super().receive_image(image, metadata)
