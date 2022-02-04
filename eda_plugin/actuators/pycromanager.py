"""Actuator based on the remote acquisition capabilities of Pycromanager and Micro-Magellan.

This implementation uses the post_hardware_hook_fn and image_process_fn hooks in
pycromanager.Acquisition to change the interval and receive images from Micro-Manager.

See also:
pycromanager (https://github.com/micro-manager/pycro-manager)
Micro-Magellan (https://micro-manager.org/MicroMagellan)
"""

import pycromanager
import copy
import queue
import logging
from PyQt5.QtCore import pyqtSignal

from eda_plugin.utility.data_structures import PyImage
from eda_plugin.actuators.micro_manager import MMAcquisition


log = logging.getLogger("EDA")


class PycroAcquisition(MMAcquisition):
    """MMAcquisition that can be used with actuators.micro_manager.MMActuator.

    This implementation of a MMAcquisition uses the remote acquisition interplay between
    pycromanager (https://github.com/micro-manager/pycro-manager) and Micro-Magellan
    (https://micro-manager.org/MicroMagellan). An image_process_fn receives the images recorded and
    sends them to the analyser. A post_hardware_hook gives the possibility to change a capture
    event. This is used to add another image event with the interval that is currently requested by
    the interpreter.
    """

    new_image = pyqtSignal(PyImage)
    acquisition_started_event = pyqtSignal(object)

    def __init__(self, studio, start_interval: float = 5.0, settings=None):
        """Set default settings, set up first acquisiton events connect signals."""
        super().__init__(studio)
        if settings is None:
            settings = {
                "num_time_points": 2,
                "time_interval_s": start_interval,
                "channel_group": "Channel",
                "channels": ["FITC", "DAPI"],
                "order": "tc",
            }
        self.events = pycromanager.multi_d_acquisition_events(**settings)
        self.channels = [
            self.events[i]["channel"] for i in range(len(settings["channels"]))
        ]
        self.start_timepoints = settings["num_time_points"]

        self.interval = start_interval
        self.stop_acq_condition = False
        self.last_arrival_time = None
        self.new_image.connect(self.event_bus.new_image_event)

    def start_acq(self):
        """Start acquisition."""
        # TODO: The save_path should be possible to set from the outside
        self.acquisition = pycromanager.Acquisition(
            directory="C:/Users/stepp/Desktop/eda_save",
            name="acquisition_name",
            # magellan_acq_index=0,
            post_hardware_hook_fn=self.post_hardware,
            image_process_fn=self.receive_image,
            show_display=True,
        )
        self.acquisition.acquire(self.events)

    def stop_acq(self):
        """Stop acquisition.

        If there would still be many events in the acquisition queue, this would not be trivial.
        Works here, as this implementation only generates the next event and can then pass None.
        https://github.com/micro-manager/pycro-manager/issues/340
        """
        self.stop_acq_condition = True
        self.acquisition_ended.emit()

    def post_hardware(self, event, _, event_queue: queue.Queue):
        """Return the event, unless acquisition was stopped.

        If acquisition continues running, add another event with the interval present in the moment.
        """
        # Check if acquisition was stopped
        if self.stop_acq_condition:
            event_queue.put(None)
            return None
        # Add another event with the interval that is set at the moment
        if all(
            [
                event["axes"]["time"] >= self.start_timepoints - 1,
                event["channel"] == self.events[1]["channel"],
            ]
        ):
            new_event = copy.deepcopy(event)
            if self.interval > 0:
                new_event["min_start_time"] = event["min_start_time"] + self.interval
            else:
                new_event["min_start_time"] = self.last_arrival_time + self.interval
            new_event["axes"]["time"] = event["axes"]["time"] + 1
            for c in range(2):
                new_event["channel"] = self.channels[c]
                new_event["axes"]["channel"] = c
                event_queue.put(copy.deepcopy(new_event))
        return event

    def receive_image(self, image, metadata):
        """Extract relevant metadata, make utility.data_sctructures.PyImage and notify EventBus."""
        for idx, c in enumerate(self.channels):
            if metadata["Channel"] == c["config"]:
                channel = idx
        py_image = PyImage(
            image,
            metadata["Axes"]["time"],
            channel,
            metadata["SliceIndex"],
            metadata["ElapsedTime-ms"],
        )
        self.new_image.emit(py_image)
        self.last_arrival_time = metadata["ElapsedTime-ms"] / 1000
        log.debug(f"timepoint {py_image.timepoint} - new image")
        return image, metadata

    def change_interval(self, new_interval):
        """Change the internal interval."""
        self.interval = new_interval
