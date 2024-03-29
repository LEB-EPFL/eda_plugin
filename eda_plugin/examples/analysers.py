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
from skimage import exposure, filters, transform, measure, segmentation, morphology

import logging
import time

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


class KerasTester(KerasWorker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        network_input = self.prepare_images(self.local_images)
        log.info(network_input["pixels"].shape)
        self.signals.new_network_image.emit(network_input["pixels"][0, :, :,0 ]*10_000, (self.timepoint, 0))

    def prepare_images(self, images: np.ndarray):
        log.info(images.shape) #returns a tuple containing the dimensions of the array
        # t0 = time.perf_counter()
        # int_range = (images.min(), np.percentile(images, 97))
        # print(int_range)
        # print(time.perf_counter() - t0)
        # images = exposure.rescale_intensity(images, in_range = tuple(int_range))
        t0 = time.perf_counter()
        tiles = 8
        x,y = np.meshgrid(range(tiles), range(tiles))
        x, y = x.flatten(), y.flatten()
        for i in range(tiles*tiles):
            images[x[i]*256:x[i]*256 + 256,
                    y[i]*256:y[i]*256 + 256] = exposure.rescale_intensity(images[x[i]*256:x[i]*256 + 256,
                                                                                 y[i]*256:y[i]*256 + 256])
        print("rescale time:, ", time.perf_counter() - t0)
        # images = exposure.rescale_intensity(images, (images.min(), 7_000))
        log.info("BEFORE RESHAPE " + str(images.shape))
        images = images[:, :, 0, 0, :]
        data = {"pixels": np.expand_dims(images, 0)}
        log.info(data['pixels'].shape)
        # log.debug(f"timepoint {self.timepoint} images prepared")
        return data

class Keras1CWorker(KerasWorker):
    """A KerasWorker with background subtraction and intensity normalization before inference."""

    def __init__(self, *args, **kwargs):
        """Call the init function of KerasWorker with the settings supplied on call."""
        super().__init__(*args, **kwargs)

    def prepare_images(self, images: np.ndarray):
        """Subtract background and normalize image intensity."""
        # print(f"RescaleWorker Images incoming: {images.shape}")
        images = prepare_1c(images)
        # images = images[:, :, 0]

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

    def extract_decision_parameter(self, network_output: np.ndarray):
        return np.max(network_output)

    #def run(self):
     #   network_input = self.prepare_images(self.local_images)
      #  log.info(network_input["pixels"].shape)
       # self.signals.new_network_image.emit(network_input["pixels"][0, :, :,0 ], (self.timepoint, 0))

    def prepare_images(self, images: np.ndarray):
        """Background subtraction, resize, intensity normalization and tiling."""
        # log.info(images.shape)
        images = exposure.rescale_intensity(images)
        images = images[:, :, 0]
        data = {"pixels": np.expand_dims(images, 0)}
        log.info(images.shape)
        # log.debug(f"timepoint {self.timepoint} images prepared")
        return data

    def post_process_output(self, data: np.ndarray, positions):
        """Strip off the dimensions that come from the network."""
        # print(data.shape)
        data = data/data.max()*5000
        return data[0, :, :, 0]

class TimeWorker(KerasWorker):
    """KerasWorker for timepoint data"""
    def __init__(self, *args, **kwargs):
        """Call the init function of KerasWorker with the settings supplied."""
        super().__init__(*args, **kwargs)

    def extract_decision_parameter(self, network_output: np.ndarray):
        return np.max(network_output)

    def prepare_images(self, images: np.ndarray):
        """Background subtraction, resize, intensity normalization and tiling."""
        # log.info(images.shape)
        t0 = time.perf_counter()
        orig_shape = images.shape
        tiles = 8
        tile_size = 256 # tiles*tile_size should be image size
        images = images.reshape((tiles*tiles, tile_size, tile_size, images.shape[-1])).astype(np.float32)
        for i in range(tiles*tiles):
            images[i] -= np.min(images[i])
            images[i] /= np.max(images[i])
        images = images.reshape(orig_shape)
        print("rescale time:, ", time.perf_counter() - t0)
        images = images[:, :, 0, 0, :]
        data = {"pixels": np.expand_dims(images, 0)}
        log.info(data['pixels'].shape)
        # log.debug(f"timepoint {self.timepoint} images prepared")
        return data

    def post_process_output(self, data: np.ndarray, positions):
        """Strip off the dimensions that come from the network."""
        # print(data.shape)
        if self.mask is not None:
            data[0, :, :, 0] = data[0, :, :, 0]*self.mask
        data = data*10000
        return data[0, :, :, 0].astype(np.uint16)
    

class PDAWorker(KerasWorker):
    """A KerasWorker for pearling detection that outputs the size of the biggest detected event.
    Includes background subtraction and intensity normalization before inference."""

    def __init__(self, *args, **kwargs):
        """Call the init function of KerasWorker with the settings supplied on call."""
        super().__init__(*args, **kwargs)
        self.threshold = 0.25

    def prepare_images(self, images: np.ndarray):
        """Subtract background and normalize image intensity."""
        # print(f"RescaleWorker Images incoming: {images.shape}")
        images = images - images.min()
        images = images/images.max()
        data = {"pixels": np.expand_dims(images, 0)}
        return data

    def extract_decision_parameter(self, network_output: np.ndarray):
        thresh_otsu = filters.threshold_otsu(network_output)
        thresh = self.threshold
        print(network_output.max())
        print(thresh_otsu)
        bw = network_output[0,:,:,0] > thresh
        cleared = segmentation.clear_border(bw)
        label_image = measure.label(cleared)
        regions = measure.regionprops(label_image)
        sizes = []
        for region in regions:
            sizes.append(region.area)
        try:
            maximum = np.max(sizes)
        except ValueError:
            maximum = 0
        return maximum

    def post_process_output(self, data: np.ndarray, positions):
        """Strip off the dimensions that come from the network."""
        data = data[0,:,:,0] > self.threshold
        return data