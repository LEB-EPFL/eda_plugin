"""Image analyser that also delivers the position of the event.

In the original implementation written for the ZenActuator, but would also work for other actuators that
know how to handle the position."""


from eda_plugin.analysers.image import ImageAnalyser, ImageAnalyserWorker
from qtpy.QtCore import QThread, Signal, Slot, QObject
from eda_plugin.utility.event_bus import EventBus

from eda_plugin.utility.data_structures import EDAEvent
import time
import numpy as np
import logging
import pyclesperanto_prototype as cle
from eda_plugin.analysers.fusion_focus import pipeline

log = logging.getLogger("EDA")

class PositionAnalyser(ImageAnalyser):
    """Take as much functionality as possible from the ImageAnalyser, but add the position of the event."""
    new_decision_parameter = Signal(object)

    def __init__(self, event_bus: EventBus):
        """Initialize the ImageAnalyser and connect the new event that includes the position."""
        # pythoncom.CoInitialize()
        super().__init__(event_bus)
        self.worker = PositionAnalyserWorker

        # self.new_decision_parameter.connect(event_bus.new_decision_parameter)

    def init_settings(self, event_bus: EventBus):
        """Don't try to get the settings from MicroManager, as this was written for Zen"""
        #TODO: Make this a composition thing, not an inheritance thing.
        pass


class PositionAnalyserWorker(ImageAnalyserWorker):
    """Add the position information to the ImageAnalyserWorker"""

    def __init__(self, local_images: np.ndarray, timepoint: int, start_time: int):
        super().__init__(local_images, timepoint, start_time)

    def run(self):
        """Get the maximum pixel value and position of the passed images and return."""
        decision_parameter, position = self.extract_decision_parameter(self.local_images)
        elapsed_time = round(time.time() * 1000) - self.start_time
        logging.info(f"New decision parameter: {decision_parameter}")

        # if self.timepoint > 10:
        #     neg_adjustment = (self.timepoint - 13)**5
        # else:
        #     neg_adjustment = 0
        # decision_parameter = (self.timepoint + 3)**3 + decision_parameter - neg_adjustment
        event = EDAEvent(decision_parameter, position, elapsed_time/1000, self.timepoint)
        self.signals.new_decision_parameter.emit(event)        

    def extract_decision_parameter(self, images: np.ndarray):
        """Return the first value of the ndarray."""
        # images = cle.gaussian_blur(images[:, :, 0, 0], sigma_x=3, sigma_y=3)
        #pos = np.unravel_index(np.argmax(images), images.shape)
        images = images[:, : , 0, 0]
        pos = pipeline(images)[:,0]
        pos = [int(x) for x in pos]
        print(pos)
        value = images[pos[0], pos[1]]
        pos = (pos[1] - images.shape[1]/2, pos[0] - images.shape[0]/2)
        return value, pos

    class _Signals(QObject):
        """Modify the original signal to include the position"""
        new_decision_parameter = Signal(EDAEvent)