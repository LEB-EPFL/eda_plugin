"""Communication hub for the different parts of the EDA loop.

Also handles the connection to the EventThread that receives events from Micro-Manager via the
PythonEventServer plugin provided.
"""
import logging
from PyQt5.QtCore import QObject, pyqtSignal

from pymm_eventserver.data_structures import ParameterSet, PyImage

from pymm_eventserver.event_thread import EventThread
from eda_plugin.utility.event_threads import ZenEventThread
import numpy as np
from typing import Union, List

log = logging.getLogger("EDA")

class EventBus(QObject):
    """Mainly a hub for incoming events that can be subscribed to."""

    # Interpreter Events
    new_interpretation = pyqtSignal(float)
    new_parameters = pyqtSignal(ParameterSet)

    # Events from micro-manager via EventThread
    acquisition_started_event = pyqtSignal(object)
    acquisition_ended_event = pyqtSignal(object)
    new_image_event = pyqtSignal(PyImage)
    mda_settings_event = pyqtSignal(object)
    configuration_settings_event = pyqtSignal(str, str, str)

    # Analyser Events
    new_decision_parameter = pyqtSignal(object)
    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray, tuple)

    # Magellan Events
    new_magellan_settings = pyqtSignal(dict)

    # Zen Events
    reset_data = pyqtSignal()

    def __init__(self, event_thread: EventThread = EventThread,
                 subscribe_to: Union[str, List] = "all"):
        """Connect to Micro-Manager using the EventThread. Pass these signals through to subs."""
        super().__init__()
        if subscribe_to == "all":
            topics = ["StandardEvent", "GUIRefreshEvent", "Acquisition", "GUI", "Settings",
                      "NewImage"]
        else:
            topics = subscribe_to

        if event_thread == EventThread:
            self.event_thread = event_thread(topics=topics)
        elif event_thread == ZenEventThread:
            self.zen_id = topics
            self.event_thread = event_thread(self)
        
        # This will only work for the Micro-Manager event thread
        try:
            self.studio = self.event_thread.bridge.get_studio()
        except AttributeError:
            self.studio = None

        # This is the event every Event_Thread will have to implement
        self.event_thread.listener.new_image_event.connect(self.new_image_event)

        # Optional things
        try:
            self.event_thread.listener.acquisition_started_event.connect(self.acquisition_started_event)
            self.event_thread.listener.acquisition_ended_event.connect(self.acquisition_ended_event)
            self.event_thread.listener.mda_settings_event.connect(self.mda_settings_event)
            self.event_thread.listener.configuration_settings_event.connect(
                self.configuration_settings_event
            )
            self.new_decision_parameter.connect(self.listen_events)
        except AttributeError:
            log.info("Some events could not be connected")

        self.initialized = True
        print("EventBus ready")
        # self.mda_settings_event.emit(settings)

    def listen_events(self, evt):
        logging.info("Event arrived in EventBus")
        logging.info(evt)


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
