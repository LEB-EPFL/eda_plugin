"""Output for EDA experiments to store all the relevant information in one place.Based on ome-ngff
https://www.nature.com/articles/s41592-021-01326-w
"""


import logging
import os
import numpy as np

import tifffile
import glob
from ome_zarr import io, writer
import zarr

from qtpy.QtCore import QObject
from qtpy import QtWidgets
from eda_plugin.utility.data_structures import MMSettings, PyImage
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.qt_classes import QWidgetRestore


log = logging.getLogger("EDA")


class Writer(QObject):
    """Writer that writes images, metadata and EDA specific data to have all information for an EDA
    experiment in one place."""

    # TODO: Does this now save the images itself, or does it take the Micro-Manager output?

    def __init__(self, event_bus: EventBus):
        """Connect the necessary signals"""
        super().__init__()
        self.event_bus = event_bus

        # TODO: Put/Get these things into/from a WriterGUI
        self.PATH = "C:/Users/stepp/Documents/02_RAW/SmartMito/"
        self.gui = WriterGUI(self)

        self.event_bus.new_decision_parameter.connect(self.save_decision_parameter)
        self.event_bus.acquisition_started_event.connect(self.new_save_location)
        self.event_bus.new_image_event.connect(self.save_image)
        self.event_bus.new_network_image.connect(self.save_network_image)
        self.event_bus.acquisition_ended_event.connect(self.save_ome_metadata)

        self.store = None
        self.root = None
        self.local_image_store = None

    def new_save_location(self, event):
        """A new acquisition was started leading to a new path for saving"""
        self.settings = MMSettings(event.get_settings())
        self.orig_save_path = event.get_datastore().get_save_path()
        writer_path = os.path.join(self.PATH, os.path.basename(self.orig_save_path) + ".ome.zarr")
        self.root = self._zarr_group(writer_path)

        self.eda_root = self._zarr_group(writer_path, "EDA")
        self.eda_root.create_dataset("analyser_output", shape=(1, 2))  # for analyser output

        self.ome_root = self._zarr_group(writer_path, "OME")
        self.image_root = self._zarr_group(writer_path, "Images")

        log.info("New writer path " + writer_path)

    def save_image(self, py_image: PyImage):
        """Gather one timepoint for the original data and save it."""
        if all([py_image.timepoint == 0, py_image.channel == 0, py_image.z_slice == 0]):
            shape = (1, 2, 1, py_image.raw_image.shape[-2], py_image.raw_image.shape[-1])
            self.image_root.create_dataset("0", shape=shape, dtype=">u2")
            self._fake_metadata(py_image.raw_image.shape, self.image_root, "0")
            self.local_image_store = np.ndarray(shape)

        self.local_image_store[0][py_image.channel][py_image.z_slice] = py_image.raw_image

        if (
            py_image.channel == self.settings.n_channels - 1
            and py_image.z_slice == self.settings.n_slices - 1
        ):
            if py_image.timepoint == 0:
                self.image_root["0"] = self.local_image_store
            else:
                self.image_root["0"].append(self.local_image_store)

    def save_network_image(self, image: np.ndarray, dims: tuple):
        """Save network image to zarr store"""
        # -> Put this into a function so we can adjust it when subclassing
        image = self.prepare_nn_image(image, dims)

        if dims[0] == 0:
            self.eda_root.create_dataset(
                "nn_images", shape=(1, 1, 1, image.shape[0], image.shape[1])
            )
            self._fake_metadata(image.shape, self.eda_root, "nn_images")

        image = np.expand_dims(image, axis=[0, 1, 2])

        while dims[0] > self.eda_root["nn_images"].shape[0] - 1:
            # A frame was missed, lets add an empty frame
            log.warning("Frame missed, saving empty nn image!")
            self.eda_root["nn_images"].append(np.zeros_like(image))

        if dims[0] == 0:
            self.eda_root["nn_images"] = image
        else:
            self.eda_root["nn_images"].append(image)

    def save_decision_parameter(self, param: float, elapsed: float, timepoint: int):
        "Received new interpretation from interpreter, save value into the EDA file"
        # TODO: be careful, might not get all the params!
        self.eda_root["analyser_output"].append([[timepoint, param]])

    def prepare_nn_image(self, image, dims):
        """Padding here, could be something else in a subclass.

        Note, that the cropping was done at the end of the image in the KerasRescaleWorker.
        """
        diff = tuple(map(lambda i, j: i - j, self.local_image_store.shape[-2:], image.shape))
        if not diff == (0, 0):
            image = np.pad(image, ((0, diff[0]), (0, diff[1])))
        return image

    def save_ome_metadata(self):
        """Get the OME metadata from the original tiff file and save it"""
        metadata_file = "METADATA.ome.xml"
        tif_file = glob.glob(self.orig_save_path + "/*.ome.tif")[0]
        with tifffile.TiffFile(tif_file) as tif:
            xml_metadata = tif.ome_metadata

        # This might be to naive, bioformats2raw does some more things here.
        ome_path = os.path.join(self.ome_root.store.path, metadata_file)
        with open(ome_path, "w", encoding="utf-8") as f:
            f.write(xml_metadata)

    def _zarr_group(self, path: str, name: str = None) -> zarr.Group:
        path = path + "/" + name if name is not None else path
        store = io.parse_url(path, mode="w").store
        root = zarr.group(store=store)
        return root

    def _fake_metadata(self, shape, group, name="0"):
        axes = ["t", "c", "z", "x", "y"]
        shapes = [[1, 2, 1, shape[-2], shape[-1]]]
        coordinate_transformations = writer.CurrentFormat().generate_coordinate_transformations(
            shapes
        )
        datasets = [{"path": name, "coordinateTransformations": coordinate_transformations[0]}]
        writer.write_multiscales_metadata(group, datasets, writer.CurrentFormat(), axes)


class WriterGUI(QWidgetRestore):
    """GUI to set the save location and what to save"""

    def __init__(self, writer: Writer):
        super().__init__()

        self.model_label = QtWidgets.QLabel("Save Path")
        self.model = QtWidgets.QLineEdit(writer.PATH)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.model_label)
        self.layout().addWidget(self.model)
        # TODO: make this functional
