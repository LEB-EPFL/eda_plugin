from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from data_structures import ParameterSet

from isimgui.event_thread import EventThread
from isimgui.data_structures import PyImage
import numpy as np

class EventBus(QObject):

    # Interpreter Events
    new_interpretation = pyqtSignal(float)
    new_parameters = pyqtSignal(ParameterSet)

    #Events from micro-manager via EventThread
    acquisition_started_event = pyqtSignal(object)
    acquisition_ended_event = pyqtSignal(object)
    new_image_event = pyqtSignal(PyImage)

    #Analyser Events
    new_decision_parameter = pyqtSignal(float, float, int)
    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray)


    def __init__(self):
        super().__init__()
        self.event_thread = EventThread()
        self.event_thread.start()
        self.studio = self.event_thread.bridge.get_studio()

        self.event_thread.acquisition_started_event.connect(self.acquisition_started_event)
        self.event_thread.acquisition_ended_event.connect(self.acquisition_ended_event)
        self.event_thread.new_image_event.connect(self.new_image_event)
