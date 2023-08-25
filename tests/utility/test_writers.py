import glob
import io
import os
import shutil
import time

import numpy as np
import ome_types
import pytest

from eda_plugin.utility.writers import Writer
from ome_zarr.io import parse_url
from ome_zarr.reader import Reader
from pymm_eventserver.data_structures import  PyImage



@pytest.fixture
def writer_plugin(event_bus):
    widget = Writer(event_bus=event_bus)
    yield widget


def test_new_save_location(writer_plugin, java_settings_event):
    assert writer_plugin.settings is None
    # Calling with saving off has to make a new file name and create all the folders there
    writer_plugin.new_save_location(java_settings_event)
    writer_plugin.new_save_location(java_settings_event)


def test_new_save_location_here(writer_plugin, java_settings_event_w_save_loc):
    assert writer_plugin.settings is None
    # Calling with saving off has to make a new file name and create all the folders there
    writer_plugin.new_save_location(java_settings_event_w_save_loc)
    writer_plugin.new_save_location(java_settings_event_w_save_loc)
    writer_plugin.new_save_location(java_settings_event_w_save_loc)


def test_full(writer_plugin, java_settings_event_w_save_loc):

    # Acquisition is started
    # writer_plugin.event_bus.acquisition_started_event.emit(None)
    writer_plugin.event_bus.acquisition_started_event.emit(java_settings_event_w_save_loc)

    # Image arrives
    first_frame = (np.random.rand(1024, 1024)*2000).astype(np.uint16)
    writer_plugin.event_bus.new_image_event.emit(PyImage(first_frame, {}, 0, 0, 0, 1023))
    time.sleep(0.2)
    writer_plugin.event_bus.new_image_event.emit(PyImage((np.random.rand(1024, 1024)*255).astype(np.uint16), {}, 0, 1, 0, 1123))
    time.sleep(0.2)
    writer_plugin.event_bus.new_network_image.emit(np.random.rand(1024, 1024), (0, 0))
    time.sleep(0.2)
    writer_plugin.event_bus.new_image_event.emit(PyImage((np.random.rand(1024, 1024)*255).astype(np.uint16), {}, 1, 0, 0, 2023))
    time.sleep(0.2)
    writer_plugin.event_bus.new_image_event.emit(PyImage((np.random.rand(1024, 1024)*255).astype(np.uint16), {}, 1, 1, 0, 2123))

    nn_image = np.random.rand(1024, 1024)*255
    # Network image arrives from analyser
    writer_plugin.event_bus.new_network_image.emit(nn_image, (0, 0))

    #Acquisition Ended
    writer_plugin.event_bus.acquisition_ended_event.emit(None)

    time.sleep(1)

    folders = sorted(glob.glob(os.path.dirname(__file__) + "/../data/FOV*.ome.zarr"))
    folder = folders[-1]

    # Check if the first image is there
    reader = Reader(parse_url(folder + "/Images"))
    nodes = list(reader())
    arr = np.asarray(nodes[0].data[0][0, 0, 0])
    assert np.array_equal(first_frame, arr)

    # Check if the neural network image is there
    reader = Reader(parse_url(folder + "/EDA/nn_images"))
    nodes = list(reader())
    arr = np.asarray(nodes[0].data[0][0, 0, 0])
    assert np.array_equal(nn_image, arr)

    # Check if valid OME metadata was written
    ome_xml = folder + "/OME/METADATA.ome.xml"
    with io.open(ome_xml, mode='r', encoding='utf-8') as f:
        xml = f.read()
        ome_types.validate_xml(xml)



def test_clean_up():
    folder = os.path.dirname(os.path.dirname(__file__)) + "/data"
    for subfolder in os.listdir(folder):
        try:
            shutil.rmtree(os.path.join(folder, subfolder))
        except NotADirectoryError:
            os.remove(os.path.join(folder, subfolder))
