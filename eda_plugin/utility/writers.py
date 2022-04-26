"""Output for EDA experiments to store all the relevant information in one place.Based on ome-ngff
https://www.nature.com/articles/s41592-021-01326-w
"""


import logging
import os
import numpy as np

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

        # TODO: Put/Get these things into a WriterGUI
        self.PATH = "C:/Users/stepp/Documents/02_RAW/SmartMito/"
        self.gui = WriterGUI(self)

        self.event_bus.new_decision_parameter.connect(self.save_decision_parameter)
        self.event_bus.acquisition_started_event.connect(self.new_save_location)
        self.event_bus.new_image_event.connect(self.save_image)
        self.event_bus.new_network_image.connect(self.save_network_image)

        self.store = None
        self.root = None
        self.local_image_store = None

    def new_save_location(self, event):
        """A new acquisition was started leading to a new path for saving"""
        self.settings = MMSettings(event.get_settings())
        save_path = event.get_datastore().get_save_path()
        writer_path = os.path.join(self.PATH, os.path.basename(save_path) + ".ome.zarr")
        self.store = io.parse_url(writer_path, mode="w").store
        self.eda_root = zarr.group(store=self.store, path="EDA")
        self.eda_root.create_dataset(
            "analyser_output", shape=(1, 2)
        )  # for analyser output

        # Prepare for writing received images
        self.image_store = io.parse_url(writer_path + "/Images", mode="w").store
        self.image_root = zarr.group(store=self.image_store)

        log.info("New writer path" + writer_path)

    def save_image(self, py_image: PyImage):
        if all([py_image.timepoint == 0, py_image.channel == 0, py_image.z_slice == 0]):
            self.image_root.create_dataset(
                "0",
                shape=(
                    1,
                    2,
                    1,
                    py_image.raw_image.shape[-2],
                    py_image.raw_image.shape[-1],
                ),
            )
            self._fake_metadata(py_image.raw_image.shape, self.image_root, "0")
            self.local_image_store = np.ndarray(
                (
                    1,
                    self.settings.n_channels,
                    self.settings.n_slices,
                    py_image.raw_image.shape[-2],
                    py_image.raw_image.shape[-1],
                )
            )
        self.local_image_store[0][py_image.channel][
            py_image.z_slice
        ] = py_image.raw_image

        if all(
            [
                py_image.channel == self.settings.n_channels - 1,
                py_image.z_slice == self.settings.n_slices - 1,
            ]
        ):
            self.image_root["0"].append(self.local_image_store)
            print(self.image_root["0"].shape)
            print(self.local_image_store.shape)

    def save_network_image(self, image: np.ndarray, dims: tuple):
        """Save network image to zarr store"""
        if dims[0] == 0:
            self.eda_root.create_dataset(
                "nn_images", shape=(1, 1, 1, image.shape[0], image.shape[1])
            )
            self._fake_metadata(image.shape, self.eda_root, "nn_images")
        image = np.expand_dims(image, axis=[0, 1, 2])
        # TODO: Check tyhat we append at the correct position, analysis might have been skipped
        # TODO: pad the image in case it is smaller than the original one.
        self.eda_root["nn_images"].append(image)

    def save_decision_parameter(self, param: float, elapsed: float, timepoint: int):
        "Received new interpretation from interpreter, save value into the EDA file"
        # TODO: be careful, might not get all the params!
        self.eda_root["analyser_output"].append([[timepoint, param]])

    def _fake_metadata(self, shape, group, name="0"):
        axes = ["t", "c", "z", "x", "y"]
        shapes = [[1, 2, 1, shape[-2], shape[-1]]]
        coordinate_transformations = (
            writer.CurrentFormat().generate_coordinate_transformations(shapes)
        )
        datasets = [
            {"path": name, "coordinateTransformations": coordinate_transformations[0]}
        ]
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
