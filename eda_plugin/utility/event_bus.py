"""Communication hub for the different parts of the EDA loop.

Also handles the connection to the EventThread that receives events from Micro-Manager via the
PythonEventServer plugin provided.
"""

from qtpy.QtCore import QObject, Signal
from pymm_eventserver.data_structures import ParameterSet, PyImage

from pymm_eventserver.event_thread import EventThread
import numpy as np
from typing import Union, List


class EventBus(QObject):
    """Mainly a hub for incoming events that can be subscribed to."""

    # Interpreter Events
    new_interpretation = Signal(float)
    new_parameters = Signal(ParameterSet)

    # Events from micro-manager via EventThread
    new_acquisition_started_event = Signal(object)
    acquisition_started_event = Signal(object)
    acquisition_ended_event = Signal(object)
    new_image_event = Signal(PyImage)
    mda_settings_event = Signal(object)
    configuration_settings_event = Signal(str, str, str)

    # Analyser Events
    new_decision_parameter = Signal(float, float, int)
    new_output_shape = Signal(tuple)
    new_network_image = Signal(np.ndarray, tuple)
    new_prepared_image = Signal(np.ndarray, int)

    # Magellan Events
    new_magellan_settings = Signal(dict)

    def __init__(self, event_thread: EventThread = EventThread,
                 subscribe_to: Union[str, List] = "all"):
        """Connect to Micro-Manager using the EventThread. Pass these signals through to subs."""
        super().__init__()
        if subscribe_to == "all":
            topics = ["StandardEvent", "GUIRefreshEvent", "Acquisition", "GUI", "Settings",
                      "NewImage"]
        else:
            topics = subscribe_to
        self.event_thread = event_thread(topics=topics)

        self.studio = self.event_thread.listener.studio

        self.event_thread.listener.acquisition_started_event.connect(self.acquisition_started_event)
        self.event_thread.listener.acquisition_ended_event.connect(self.acquisition_ended_event)
        self.event_thread.listener.new_image_event.connect(self.new_image_event)

        self.event_thread.listener.mda_settings_event.connect(self.mda_settings_event)
        self.event_thread.listener.configuration_settings_event.connect(
            self.configuration_settings_event
        )

        self.initialized = True
        print("EventBus ready")
        # self.mda_settings_event.emit(settings)


def main():
    import time

    thread = EventThread
    bus = EventBus(thread)
    while True:
        try:
            time.sleep(0.01)
        except KeyboardInterrupt:
            bus.__dict__
            thread.listener.stop()
            print("Stopping")
            break
