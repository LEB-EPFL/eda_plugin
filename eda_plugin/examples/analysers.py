"""Examples of using the KerasWorker QRunnable to add on pre and post-processing steps."""

from multiprocessing.spawn import prepare
import numpy as np

from eda_plugin.analysers.keras import KerasWorker
from eda_plugin.utility.image_processing import (
    prepare_ftsw,
    prepareNNImages,
    stitchImage,
    prepare_wo_tiling,
    prepare_1c
)
from skimage import exposure, filters, transform

import logging

log = logging.getLogger("EDA")


class KerasRescaleWorker(KerasWorker):
    """A KerasWorker with background subtraction and intensity normalization before inference."""

    def __init__(self, *args, **kwargs):
        """Call the init function of KerasWorker with the settings supplied on call."""
        super().__init__(*args, **kwargs)

    def prepare_images(self, images: np.ndarray):
        """Subtract background and normalize image intensity."""
        # print(f"RescaleWorker Images incoming: {images.shape}")
        images = prepare_wo_tiling(images)
        images = images[:, :, :, 0]
        data = {"pixels": np.expand_dims(images, 0)}
        return data

    def extract_decision_parameter(self, network_output: np.ndarray):
        return np.max(network_output)

    def post_process_output(self, data: np.ndarray, positions):
        """Strip off the dimensions that come from the network."""
        # print(data.shape)
        return data[0, :, :, 0]


class Keras1CWorker(KerasWorker):
    """A KerasWorker with background subtraction and intensity normalization before inference."""

    def __init__(self, *args, **kwargs):
        """Call the init function of KerasWorker with the settings supplied on call."""
        super().__init__(*args, **kwargs)

    def prepare_images(self, images: np.ndarray):
        """Subtract background and normalize image intensity."""
        # print(f"RescaleWorker Images incoming: {images.shape}")
        images = prepare_1c(images)
        images = images[:, :, 0]
        data = {"pixels": np.expand_dims(images, 0)}
        return data

    def extract_decision_parameter(self, network_output: np.ndarray):
        return np.max(network_output)

    def post_process_output(self, data: np.ndarray, positions):
        """Strip off the dimensions that come from the network."""
        # print(data.shape)
        return data[0, :, :, 0]


class KerasTilingWorker(KerasWorker):
    """KerasWorker with pre and postprocessing.

    Add background subtraction, resize, intensity normalization and tiling to preprocessing.
    Add Stitching to the postprocessing.
    """

    def __init__(self, *args, **kwargs):
        """Call the init function of KerasWorker with the settings supplied."""
        super().__init__(*args, **kwargs)

    def post_process_output(self, network_output: np.ndarray, input_data) -> np.ndarray:
        """Stitch the images recevied from the network to an array with the same size as input."""
        prep = stitchImage(network_output, input_data["positions"])
        return prep

    def extract_decision_parameter(self, network_output: np.ndarray):
        return np.max(network_output)

    def prepare_images(self, images: np.ndarray):
        """Background subtraction, resize, intensity normalization and tiling."""
        tiles, positions = prepareNNImages(images[:, :, 0], images[:, :, 1], self.model)
        data = {"pixels": tiles, "positions": positions}
        log.debug(f"timepoint {self.timepoint} images prepared")
        return data


class FtsWWorker(KerasWorker):
    """KerasWorker using the specialized pre processing for FtsW caulobacter."""

    def __init__(self, *args, **kwargs):
        """Call the init function of KerasWorker with the settings supplied."""
        super().__init__(*args, **kwargs)

    def post_process_output(self, network_output: np.ndarray, input_data) -> np.ndarray:
        """Stitch the images recevied from the network to an array with the same size as input."""
        prep = stitchImage(input_data["pixels"], input_data["positions"], channel=1)
        return prep

    def extract_decision_parameter(self, network_output: np.ndarray):
        return np.max(network_output)

    def prepare_images(self, images: np.ndarray):
        """Background subtraction, resize, intensity normalization and tiling."""
        tiles, positions = prepare_ftsw(images[:, :, 1], images[:, :, 0], self.model)
        data = {"pixels": tiles, "positions": positions}
        log.debug(f"timepoint {self.timepoint} images prepared")
        return data
