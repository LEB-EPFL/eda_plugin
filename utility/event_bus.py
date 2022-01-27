from PyQt5.QtCore import QObject, pyqtSignal
from utility.data_structures import ParameterSet

from utility.event_thread import EventThread
from utility.data_structures import PyImage
import numpy as np


class EventBus(QObject):

    # Interpreter Events
    new_interpretation = pyqtSignal(float)
    new_parameters = pyqtSignal(ParameterSet)

    # Events from micro-manager via EventThread
    acquisition_started_event = pyqtSignal(object)
    acquisition_ended_event = pyqtSignal(object)
    new_image_event = pyqtSignal(PyImage)
    # mda_settings_event = pyqtSignal(object)
    configuration_settings_event = pyqtSignal(str, str, str)

    # Analyser Events
    new_decision_parameter = pyqtSignal(float, float, int)
    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray, tuple)

    def __init__(self):
        super().__init__()
        self.event_thread = EventThread()

        self.studio = self.event_thread.bridge.get_studio()

        self.event_thread.listener.acquisition_started_event.connect(
            self.acquisition_started_event
        )
        self.event_thread.listener.acquisition_ended_event.connect(
            self.acquisition_ended_event
        )
        self.event_thread.listener.new_image_event.connect(self.new_image_event)

        # self.event_thread.listener.mda_settings_event.connect(self.mda_settings_event)
        self.event_thread.listener.configuration_settings_event.connect(self.configuration_settings_event)