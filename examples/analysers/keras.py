"""Examples of using the KerasWorker QRunnable to add on pre and post-processing steps."""

import numpy as np

from analysers.keras import KerasWorker
from eda_original.SmartMicro.NNfeeder import prepareNNImages
from eda_original.SmartMicro.ImageTiles import stitchImage
from skimage import exposure, filters, transform


class KerasRescaleWorker(KerasWorker):
    """A KerasWorker with background subtraction and intensity normalization before inference."""

    def __init__(
        self, model, local_images: np.ndarray, timepoint: int, start_time: float
    ):
        """Call the init function of KerasWorker with the settings supplied on call."""
        super().__init__(model, local_images, timepoint, start_time)

    def prepare_images(self, images: np.ndarray):
        """Subtract background and normalize image intensity."""
        sig = 121.5 / 81
        out_range = (0, 1)

        for idx in range(images.shape[-1]):
            image = images[:, :, idx]
            # resc_image = transform.rescale(image, resize_param)
            image = filters.gaussian(image, sig)
            if idx == 1:
                image = image - filters.gaussian(images[:, :, idx], sig * 5)
            in_range = (
                (image.min(), image.max()) if idx == 1 else (image.mean(), image.max())
            )
            image = exposure.rescale_intensity(image, in_range, out_range=out_range)
            images[:, :, idx] = image
        data = {"pixels": np.expand_dims(images, 0)}
        return data

    def post_process_output(self, data: np.ndarray, positions):
        """Strip off the dimensions that come from the network."""
        return data[0, :, :, 0]


class KerasTilingWorker(KerasWorker):
    """KerasWorker with pre and postprocessing.

    Add background subtraction, resize, intensity normalization and tiling to preprocessing.
    Add Stitching to the postprocessing.
    """

    def __init__(
        self, model, local_images: np.ndarray, timepoint: int, start_time: float
    ):
        """Call the init function of KerasWorker with the settings supplied."""
        super().__init__(model, local_images, timepoint, start_time)

    def post_process_output(self, network_output: np.ndarray, input_data) -> np.ndarray:
        """Stitch the images recevied from the network to an array with the same size as input."""
        return stitchImage(network_output, input_data["positions"])

    def prepare_images(self, images: np.ndarray):
        """Background subtraction, resize, intensity normalization and tiling."""
        tiles, positions = prepareNNImages(images[:, :, 0], images[:, :, 1], self.model)
        data = {"pixels": tiles, "positions": positions}
        return data


# TODO: Add the functions used here for pre/post processing directly to the module
