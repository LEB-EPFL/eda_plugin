
from pymm_eventserver.data_structures import PyImage
import numpy as np


def test_basic_config(basic_config, MMSettings_mock, java_settings_event_w_save_loc, datastore_save_path):
    py_image = PyImage(np.random.random((512,512)),{}, 0, 0, 0, 2304.)
    basic_config.event_bus.mda_settings_event.emit(MMSettings_mock)
    basic_config.event_bus.acquisition_started_event.emit(java_settings_event_w_save_loc)
    basic_config.event_bus.new_image_event.emit(py_image)
    py_image = PyImage(np.random.random((512,512)),{}, 0, 1, 0, 2304.)
    basic_config.event_bus.new_image_event.emit(py_image)
    basic_config.event_bus.new_interpretation.emit(0.3)

    basic_config.event_bus.acquisition_ended_event.emit(datastore_save_path)
