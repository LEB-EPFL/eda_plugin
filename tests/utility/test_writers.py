from logging import root
from multiprocessing import Event
from pymm_eventserver.data_structures import MMSettings, PyImage
from eda_plugin.utility.event_bus import EventBus
import pytest
import numpy as np
import os
import shutil
import time
from ome_zarr.reader import Reader
from ome_zarr.io import parse_url
import glob
from eda_plugin.utility.writers import Writer

from tests.utility.test_event_bus import event_bus, java_settings_event, java_settings_event_w_save_loc


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
    time.sleep(0.5)
    writer_plugin.event_bus.new_image_event.emit(PyImage((np.random.rand(1024, 1024)*255).astype(np.uint16), {}, 1, 0, 0, 2023))
    time.sleep(0.2)
    writer_plugin.event_bus.new_image_event.emit(PyImage((np.random.rand(1024, 1024)*255).astype(np.uint16), {}, 1, 1, 0, 2123))

    # Network image arrives from analyser
    writer_plugin.event_bus.new_network_image.emit(np.random.rand(1024, 1024), (0, 0))

    #Acquisition Ended
    writer_plugin.event_bus.acquisition_ended_event.emit(None)

    time.sleep(1)

    folders = sorted(glob.glob(os.path.dirname(__file__) + "/../data/FOV*.ome.zarr"))
    folder = folders[-1]
    store = parse_url(folder + "/Images", mode="r").store
    reader = Reader(parse_url(folder + "/Images"))
    nodes = list(reader())
    print(nodes[0].data[0][0, 0, 0])
    assert np.array_equal(first_frame, nodes[0].data[0][0, 0, 0])

    # Acquisition ended
    # TODO: This fails at the moment, because we don't have the ome.tif file to get the
    # Metadata from. We should handle this somehow anyways and get both ome and imagej metadata
    # from micro-manager direclty, if saving a tif is turned off. In the end this would be the
    # prefered way for high speed applications anyways.
    # writer_plugin.event_bus.acquisition_ended_event.emit(None)


# def test_clean_up():
#     folder = os.path.dirname(os.path.dirname(__file__)) + "/data"
#     for subfolder in os.listdir(folder):
#         try:
#             shutil.rmtree(os.path.join(folder, subfolder))
#         except NotADirectoryError:
#             os.remove(os.path.join(folder, subfolder))
