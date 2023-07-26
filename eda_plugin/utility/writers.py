"""Output for EDA experiments to store all the relevant information in one place.Based on ome-ngff
https://www.nature.com/articles/s41592-021-01326-w
"""

import copy
import glob
import json
import logging
import os
import re
from pathlib import Path
from typing import Union

import numcodecs
import numpy as np
import tifffile
import zarr
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.ome_metadata import OME
from eda_plugin.utility.qt_classes import QWidgetRestore
from ome_zarr import io, writer
from pymm_eventserver.data_structures import MMSettings, ParameterSet, PyImage
from qtpy import QtWidgets
from qtpy.QtCore import QObject, QTimer

import pdb

log = logging.getLogger("EDA")


class Writer(QObject):
    """Writer that writes images, metadata and EDA specific data to have all information for EDA.

    With this one everything will be written as OME_NGFF with some additional folders for additional
    Metadata for both Micro-Manager and EDA specific information.
    """

    def __init__(self, event_bus: EventBus):
        """Connect the necessary signals"""
        super().__init__()
        self.event_bus = event_bus

        # TODO: Put/Get these things into/from a WriterGUI

        self.gui = WriterGUI(self)

        self.event_bus.new_decision_parameter.connect(self.save_decision_parameter)
        self.event_bus.new_parameters.connect(self.update_parameters)
        self.event_bus.acquisition_started_event.connect(self.new_save_location)
        self.event_bus.new_image_event.connect(self.save_image)
        self.event_bus.new_network_image.connect(self.save_network_image)
        self.event_bus.acquisition_ended_event.connect(self.save_metadata)

        self.store = None
        self.root = None
        self.local_image_store = None
        self.params = None
        self.settings = None
        self.ome = None

    def new_save_location(self, event):
        """A new acquisition was started leading to a new path for saving"""
        if event is None:
            return
        self.settings = MMSettings(event.get_settings())

        writer_path = self._set_possible_folder_name(event)

        self.root = self._zarr_group(writer_path)

        self.eda_root = self._zarr_group(writer_path, "EDA")
        self.eda_root.create_dataset("analyser_output", shape=(1, 2))  # for analyser output
        self.eda_root.create_dataset(
            "parameters", shape=(1, 1), dtype=object, object_codec=numcodecs.JSON()
        )
        self.ome_root = self._zarr_group(writer_path, "OME")
        self.metadata_root = self._zarr_group(writer_path, "Metadata")
        self.image_root = self._zarr_group(writer_path, "Images")

        log.info("New writer path " + writer_path)

        self.ome = OME(settings=self.settings)

        self.save_thresholds()
        self.save_mmacq_settings()
        self.save_mmdev_settings(event)

    def save_image(self, py_image: PyImage):
        """Gather one timepoint for the original data and save it."""
        self.ome.add_plane_from_image(py_image)
        if not self.gui.save_images.isChecked() or py_image is None:
            return
        # if all([py_image.timepoint == 0, py_image.channel == 0, py_image.z_slice == 0,
        #         self.local_image_store is not None]) or
        if self.local_image_store is None:
            shape = (1, self.settings.n_channels, self.settings.n_slices, py_image.raw_image.shape[-2], py_image.raw_image.shape[-1])
            self.image_root.create_dataset("0", shape=shape, dtype="uint16")
            self._fake_metadata(py_image.raw_image.shape, self.image_root, "0")
            self.local_image_store = np.ndarray(shape, np.uint16)
        self.local_image_store[0, py_image.channel, py_image.z_slice, :, :] = py_image.raw_image

        if (
            py_image.channel == self.settings.n_channels - 1
            and py_image.z_slice == self.settings.n_slices - 1
        ):
            if py_image.timepoint == 0:
                self.image_root[0] = copy.deepcopy(self.local_image_store)
            else:
                self.image_root[0].append(self.local_image_store)


    def save_network_image(self, image: np.ndarray, dims: tuple):
        """Save network image to zarr store"""
        if not self.gui.save_nn_images.isChecked():
            return
        # -> Put this into a function so we can adjust it when subclassing
        image = self.prepare_nn_image(image, dims)

        if "nn_images" not in self.eda_root:
            self.eda_root.create_dataset(
                "nn_images", shape=(1, 1, 1, image.shape[0], image.shape[1])
            )
            self._fake_metadata(image.shape, self.eda_root, "nn_images")

        image = np.expand_dims(image, axis=[0, 1, 2])

        while dims[0] > self.eda_root["nn_images"].shape[0] - 1:
            # A frame was missed, lets add an empty frame
            print(dims)
            print(self.eda_root["nn_images"].shape)
            log.warning("Frame missed, saving empty nn image!")
            self.eda_root["nn_images"].append(np.zeros_like(image))

        if dims[0] == 0:
            self.eda_root["nn_images"] = image
        else:
            self.eda_root["nn_images"].append(image)

    def save_decision_parameter(self, param: float, elapsed: float, timepoint: int):
        "Received new interpretation from interpreter, save value into the EDA file"
        if not self.gui.save_nn_output.isChecked():
            return
        # TODO: be careful, might not get all the params!
        self.eda_root["analyser_output"].append([[timepoint, param]])

    def update_parameters(self, params: Union[ParameterSet, dict]):
        """Update the parameters for the Interpreter used."""
        if not isinstance(params, dict):
            self.params = params.to_dict()
        else:
            self.params = params
        log.info("Paramters updated")

    def save_thresholds(self):
        """New Acquisition is starting, save the thresholds used for this acquisition."""
        self.eda_root["parameters"] = json.dumps(self.params)

    def prepare_nn_image(self, image, dims):
        """Padding here, could be something else in a subclass.

        Note, that the cropping was done at the end of the image in the KerasRescaleWorker.
        """
        diff = tuple(map(lambda i, j: i - j, self.local_image_store.shape[-2:], image.shape))
        if not diff == (0, 0):
            image = np.pad(image, ((0, diff[0]), (0, diff[1])))
        return image

    def save_mmdev_settings(self, event):
        """Sace Micro-Manager settings"""
        file = "MM_state.txt"
        path = os.path.join(self.metadata_root.store.path, file)
        self.event_bus.studio.get_cmm_core().save_system_state(path)

    def save_mmacq_settings(self):
        """Save acquisition settings but strip off the Java objects first."""
        settings_dict = self.settings.__dict__
        settings_dict["java_channels"] = None
        settings_dict["java_slices"] = None
        settings_dict["java_settings"] = None
        settings_dict["microscope"] = None
        settings_json = json.dumps(settings_dict, indent=4, sort_keys=True)
        metadata_file = "MMSettings.json"
        path = os.path.join(self.metadata_root.store.path, metadata_file)
        with open(path, "w", encoding="utf-8") as f:
            f.write(settings_json)

    def save_metadata(self):
        """Save all the metadata once the acquisition is over."""
        try:
            tif_file = glob.glob(self.orig_save_path + "/*.ome.tif")[0]
            with tifffile.TiffFile(tif_file) as tif:
                self.save_ome_metadata(tif)
                self.save_imagej_metadata(tif)
        except IndexError:
            self.ome.finalize_metadata()
            self.save_ome_metadata(xml=self.ome.ome.to_xml())
        finally:
            # Delay this so that network images can be saved
            self.reset_timer = QTimer()
            self.reset_timer.singleShot(1000, self.reset_local_image_store)
            self.reset_timer.start()

    def reset_local_image_store(self):
        self.local_image_store = None

    def save_imagej_metadata(self, tif: Union[tifffile.TiffFile, None] = None):
        """Get the ImageJ metadata from the original tiff file and save it"""
        # Again, only works if micro-manager saved the tif in the first place
        if not self.gui.save_metadata.isChecked():
            return
        metadata_file = "imagej_metadata.json"

        if tif is not None:
            imagej_metadata = tif.imagej_metadata
        else:
            tif_file = glob.glob(self.orig_save_path + "/*.ome.tif")[0]
            with tifffile.TiffFile(tif_file) as tif:
                imagej_metadata = tif.imagej_metadata
        data = json.dumps(imagej_metadata, cls=NumpyEncoder, indent=4, sort_keys=True)
        path = os.path.join(self.metadata_root.store.path, metadata_file)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)

    def save_ome_metadata(self, tif: Union[tifffile.TiffFile, None] = None, xml: str = None):
        """Get the OME metadata from the original tiff file and save it"""
        if not self.gui.save_metadata.isChecked():
            return
        metadata_file = "METADATA.ome.xml"

        if tif is not None:
            xml_metadata = tif.ome_metadata
        elif xml is not None:
            xml_metadata = xml
        else:
            tif_file = glob.glob(self.orig_save_path + "/*.ome.tif")[0]
            with tifffile.TiffFile(tif_file) as tif:
                xml_metadata = tif.ome_metadata

        # xml_re = re.compile(r"<.*encoding>(<OME.*</OME>)")
        # xml_metadata = xml_re.search(xml_metadata).group(2)

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
        axes = ["t", "c", "z", "y", "x"]
        shapes = [[1, self.settings.n_channels, self.settings.n_slices, shape[-2], shape[-1]]]
        coordinate_transformations = writer.CurrentFormat().generate_coordinate_transformations(
            shapes
        )
        datasets = [{"path": name, "coordinateTransformations": coordinate_transformations[0]}]
        writer.write_multiscales_metadata(group, datasets, writer.CurrentFormat(), axes)

    def _set_possible_folder_name(self, event):
        folder_number = 0
        self.orig_save_path = event.get_datastore().get_save_path()

        if self.orig_save_path is None:
            self.orig_save_path = "mock/FOV"
        writer_path = os.path.join(
            self.gui.path.text(), os.path.basename(self.orig_save_path) + ".ome.zarr"
        )

        path_now = os.path.join(
            self.gui.path.text(),
            self.orig_save_path + "_" + str(folder_number).zfill(3) + ".ome.zarr",
        )
        while Path(path_now).is_dir():
            folder_number += 1
            path_now = os.path.join(
                self.gui.path.text(),
                self.orig_save_path + "_" + str(folder_number).zfill(3) + ".ome.zarr",
            )
        self.orig_save_path = self.orig_save_path + "_" + str(folder_number).zfill(3) + ".ome.zarr"
        return path_now


class WriterGUI(QWidgetRestore):
    """GUI to set the save location and what to save"""

    def __init__(self, writer: Writer):
        super().__init__()

        self.path_label = QtWidgets.QLabel("Save Path")
        self.path = QtWidgets.QLineEdit(self.settings.value("path", "C:/Users"))

        self.menu = QtWidgets.QMenu("Options")
        self.save_images = QtWidgets.QAction("Original Images", self.menu, checkable=True)
        save_images = not (self.settings.value("save_images") == "false")
        self.save_images.setChecked(save_images)
        self.save_metadata = QtWidgets.QAction("OME Metadata", self.menu, checkable=True)
        ome_metadata = not (self.settings.value("ome_metadata") == "false")
        self.save_metadata.setChecked(ome_metadata)
        self.save_nn_images = QtWidgets.QAction("Network Images", self.menu, checkable=True)
        network_images = not (self.settings.value("network_images") == "false")
        self.save_nn_images.setChecked(network_images)
        self.save_nn_output = QtWidgets.QAction("Network output", self.menu, checkable=True)
        network_output = not (self.settings.value("network_output") == "false")
        self.save_nn_output.setChecked(network_output)
        self.save_interpretations = QtWidgets.QAction("Interpretations", self.menu, checkable=True)
        interpretations = not (self.settings.value("interpretations") == "false")
        self.save_interpretations.setChecked(interpretations)
        self.menu.addActions(
            [
                self.save_images,
                self.save_metadata,
                self.save_nn_images,
                self.save_nn_output,
                self.save_interpretations,
            ]
        )
        self.menu_button = QtWidgets.QPushButton("Options")
        self.menu_button.setMenu(self.menu)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.path_label)
        self.layout().addWidget(self.path)
        self.layout().addWidget(self.menu_button)

    def closeEvent(self, e):
        self.settings.setValue("save_images", self.save_images.isChecked())
        self.settings.setValue("ome_metadata", self.save_metadata.isChecked())
        self.settings.setValue("network_images", self.save_nn_images.isChecked())
        self.settings.setValue("network_output", self.save_nn_output.isChecked())
        self.settings.setValue("interpretations", self.save_interpretations.isChecked())
        self.settings.setValue("path", self.path.text())
        return super().closeEvent(e)


class NumpyEncoder(json.JSONEncoder):
    """Small custom encoder for numpy things"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)
