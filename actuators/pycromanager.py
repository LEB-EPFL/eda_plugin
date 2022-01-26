import pycromanager
import copy
import queue
import logging
from PyQt5.QtCore import pyqtSignal

from isimgui.data_structures import PyImage
from actuators.micro_manager import MMAcquisition


log = logging.getLogger("EDA")


class PycroAcquisition(MMAcquisition):
    # """This tries to use the inbuilt Acquisition function in pycromanager. Unfortunately, these
    # acquisitions don't start with the default Micro-Manager interface and the acquisition also
    # doesn't seem to be saved in a perfect format, so that Micro-Manager would detect the correct
    # parameters to show the channels upon loading for example. The Acquisitions also don't emit any
    # of the standard Micro-Manager events. Stashed for now because of this"""

    new_image = pyqtSignal(PyImage)
    acquisition_started_event = pyqtSignal(object)

    def __init__(self, studio, start_interval: float = 5.0, settings=None):
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
        self.stop_acq_condition = True
        self.acquisition_ended.emit()

    def post_hardware(self, event, _, event_queue: queue.Queue):
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
        for idx, c in enumerate(self.channels):
            if metadata["Channel"] == c["config"]:
                channel = idx
        py_image = PyImage(
            image, metadata["Axes"]["time"], channel, metadata["ElapsedTime-ms"]
        )
        self.new_image.emit(py_image)
        self.last_arrival_time = metadata["ElapsedTime-ms"] / 1000
        log.debug(f"timepoint {py_image.timepoint} - new image")
        return image, metadata

    def change_interval(self, new_interval):
        self.interval = new_interval
